"""GitHub fetch + cache.

Retrieval strategy
------------------
- **A query plan per profile** (core/skills.py): one query per skill, using a
  strategy that suits the skill (language qualifier, or keyword in title and
  body), plus combined queries for pairs of skills that are needed together.
- **Labels OR-ed in one query** via GitHub's advanced issue search
  (``advanced_search=true``). If GitHub rejects that syntax, or it returns
  nothing where a plain query finds results, the run switches to legacy mode:
  one label per query, spent in priority order within the request budget.
- **Balanced pool**: results are interleaved per skill, so one skill with
  thousands of issues cannot crowd out another with forty.
- **Budget**: at most MAX_SEARCH_REQUESTS search calls per run, serial (as
  GitHub asks), no fixed sleeps; ``x-ratelimit-remaining`` is honoured.
- **Caching**: every response is cached for an hour; expired entries are
  revalidated with ``If-None-Match``.
- **GraphQL**: timeline lookups are batched 20 issues per call.
"""

import hashlib
import json
import os
import time

import requests

from core import db, skills

API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"
CACHE_TTL = 60 * 60          # 1 hour for search results
GRAPHQL_BATCH = 20            # GitHub node-id lookup limit per call
MAX_SEARCH_REQUESTS = 14      # stays well inside the 30/min search budget
PER_PAGE = 40
DEFAULT_POOL = 60


class GitHubError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def _http_error(resp, what):
    if resp.status_code == 401:
        return GitHubError(
            "GitHub rejected GITHUB_TOKEN (401). Check the token in .env is correct "
            "and not expired, then restart the app.", 401)
    if resp.status_code in (403, 429):
        reset_at = int(resp.headers.get("x-ratelimit-reset", time.time() + 60))
        wait = max(1, reset_at - int(time.time()))
        return GitHubError(
            f"GitHub rate limit reached. Resets in {wait}s — the app will "
            f"retry automatically. You can also search again in ~{wait}s.",
            resp.status_code,
        )
    return GitHubError(f"GitHub returned {resp.status_code} for {what}.", resp.status_code)


def github_token():
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise GitHubError(
            "GITHUB_TOKEN is missing. Copy .env.example to .env and paste "
            "your token after GITHUB_TOKEN=, then restart the app."
        )
    return token


def _headers():
    return {
        "Authorization": f"Bearer {github_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _sleep_until_reset(resp):
    """Sleep until the rate-limit window resets (hard-capped at 65s)."""
    retry_after = resp.headers.get("retry-after")
    if retry_after:
        wait = int(retry_after)
    else:
        reset = int(resp.headers.get("x-ratelimit-reset", time.time() + 10))
        wait = reset - int(time.time()) + 1
    time.sleep(max(1, min(wait, 65)))


def _guard_remaining(resp):
    """If the bucket is almost empty, pause preemptively."""
    remaining = resp.headers.get("x-ratelimit-remaining")
    if remaining is not None and int(remaining) <= 1:
        _sleep_until_reset(resp)


# ---------------------------------------------------------------- REST


def rest_get(path, params=None):
    """Cached, conditional, rate-limit aware GET against the REST API.

    When the cache has expired but still holds an ETag, we send
    ``If-None-Match``.  A 304 costs no quota on the Core API and lets us
    refresh the TTL without re-downloading the body.
    """
    cache_key = "GET " + path + "?" + json.dumps(params or {}, sort_keys=True)
    cached_body, stale_etag = db.cache_get(cache_key, CACHE_TTL)
    if cached_body is not None:
        return cached_body

    headers = _headers()
    if stale_etag:
        headers["If-None-Match"] = stale_etag

    last_resp = None
    for attempt in range(3):
        resp = requests.get(API + path, headers=headers, params=params, timeout=30)
        last_resp = resp

        if resp.status_code == 304:
            # Content unchanged — touch the cache timestamp and return stale body.
            db.cache_touch(cache_key)
            # We need the body back; re-read from cache (now fresh).
            refreshed, _ = db.cache_get(cache_key, CACHE_TTL)
            return refreshed

        if resp.status_code in (403, 429) and attempt < 2:
            _sleep_until_reset(resp)
            continue

        if resp.status_code != 200:
            raise _http_error(resp, path)

        _guard_remaining(resp)
        body = resp.json()
        etag = resp.headers.get("ETag")
        db.cache_set(cache_key, body, etag=etag)
        return body

    raise _http_error(last_resp, path)


# ---------------------------------------------------------------- GraphQL


def graphql(query, variables=None):
    """Cached, rate-limit aware GraphQL POST."""
    raw = json.dumps({"q": query, "v": variables or {}}, sort_keys=True)
    cache_key = "GQL " + hashlib.sha256(raw.encode()).hexdigest()
    cached_body, _ = db.cache_get(cache_key, CACHE_TTL)
    if cached_body is not None:
        return cached_body

    payload = {"query": query, "variables": variables or {}}
    last_resp = None
    for attempt in range(3):
        resp = requests.post(GRAPHQL, headers=_headers(), json=payload, timeout=60)
        last_resp = resp
        if resp.status_code in (403, 429) and attempt < 2:
            _sleep_until_reset(resp)
            continue
        if resp.status_code != 200:
            raise _http_error(resp, "a GraphQL query")
        body = resp.json()
        if body.get("errors") and not body.get("data"):
            raise GitHubError(f"GitHub GraphQL error: {body['errors'][0].get('message')}")
        _guard_remaining(resp)
        db.cache_set(cache_key, body)
        return body
    raise _http_error(last_resp, "a GraphQL query")


# ---------------------------------------------------------------- normalize


def _normalize(item):
    repo_full_name = item["repository_url"].split("/repos/", 1)[1]
    return {
        "id": item["id"],
        "node_id": item["node_id"],
        "number": item["number"],
        "title": item["title"],
        "body": item.get("body") or "",
        "url": item["html_url"],
        "repo_full_name": repo_full_name,
        "repo_language": None,
        "labels": [label["name"] for label in item.get("labels", [])],
        "comments_count": item.get("comments", 0),
        "created_at": item["created_at"],
        "updated_at": item["updated_at"],
        "linked_prs": [],
    }


# ---------------------------------------------------------------- timeline


_TIMELINE_QUERY = """
query($ids: [ID!]!) {
  nodes(ids: $ids) {
    ... on Issue {
      id
      repository { primaryLanguage { name } }
      timelineItems(last: 30, itemTypes: [CROSS_REFERENCED_EVENT, CONNECTED_EVENT]) {
        nodes {
          __typename
          ... on CrossReferencedEvent {
            source { ... on PullRequest { number state url } }
          }
          ... on ConnectedEvent {
            source { ... on PullRequest { number state url } }
          }
        }
      }
    }
  }
}
"""


def _attach_timeline(issues):
    """Batched GraphQL (20 issues per call): repo language and every pull
    request referenced on each issue's timeline."""
    by_node = {issue["node_id"]: issue for issue in issues}
    ids = list(by_node)
    for start in range(0, len(ids), GRAPHQL_BATCH):
        body = graphql(_TIMELINE_QUERY, {"ids": ids[start:start + GRAPHQL_BATCH]})
        for node in (body.get("data") or {}).get("nodes") or []:
            if not node or node.get("id") not in by_node:
                continue
            issue = by_node[node["id"]]
            lang = (node.get("repository") or {}).get("primaryLanguage") or {}
            issue["repo_language"] = lang.get("name")
            prs = []
            for event in node["timelineItems"]["nodes"]:
                pr = event.get("source") or {}
                if pr.get("number"):
                    prs.append({"number": pr["number"], "state": pr["state"], "url": pr["url"]})
            issue["linked_prs"] = prs


# ---------------------------------------------------------------- main entry


class _Searcher:
    """Runs planned queries within the request budget, choosing advanced or
    legacy search syntax and remembering which one works."""

    mode = os.environ.get("GITHUB_SEARCH_MODE", "").strip().lower() or None  # shared per process

    def __init__(self, budget):
        self.budget = budget
        self.log = []

    def _get(self, q, advanced):
        if self.budget <= 0:
            return None
        self.budget -= 1
        params = {"q": q, "sort": "created", "order": "desc", "per_page": PER_PAGE}
        if advanced:
            params["advanced_search"] = "true"
        return rest_get("/search/issues", params)

    def _record(self, pq, q, body):
        items = (body or {}).get("items", [])
        total = (body or {}).get("total_count", 0)
        self.log.append({"skills": list(pq.skills), "query": q, "returned": len(items), "total": total})
        return items, total

    def run_advanced(self, pq):
        q = skills.advanced_query(pq)
        try:
            body = self._get(q, advanced=True)
        except GitHubError as exc:
            if exc.status != 422:
                raise
            _Searcher.mode = "legacy"  # syntax not supported here
            return None
        if body is None:
            return [], 0
        items, total = self._record(pq, q, body)
        if total == 0 and _Searcher.mode is None:
            # Zero hits could mean the advanced syntax is silently unsupported.
            # One plain query settles it for the rest of the process.
            probe = self.run_legacy(pq, max_labels=1)
            if probe and probe[1] > 0:
                _Searcher.mode = "legacy"
                return probe
        if total > 0:
            _Searcher.mode = "advanced"
        return items, total

    def run_legacy(self, pq, max_labels=None):
        items, total = [], 0
        for label in pq.labels[:max_labels]:
            q = skills.legacy_query(pq, label)
            try:
                body = self._get(q, advanced=False)
            except GitHubError as exc:
                if exc.status == 422:
                    continue
                raise
            if body is None:
                break
            got, n = self._record(pq, q, body)
            items.extend(got)
            total += n
        return items, total


def _search_all(plan):
    """Execute the plan. Returns (results, log): results is a list of
    (PlannedQuery, items, total_count)."""
    searcher = _Searcher(MAX_SEARCH_REQUESTS)
    results = []
    pending = list(plan)
    while pending and _Searcher.mode != "legacy":
        pq = pending[0]
        outcome = searcher.run_advanced(pq)
        if outcome is None:  # switched to legacy: retry this query below
            break
        results.append((pq, *outcome))
        pending.pop(0)

    if pending:
        # Legacy syntax: one label per request. First the top label for
        # every query, then the next label for every query, until the
        # budget runs out, so no skill is starved.
        collected = {id(pq): ([], 0) for pq in pending}
        depth = max(len(pq.labels) for pq in pending)
        for i in range(depth):
            for pq in pending:
                if i >= len(pq.labels) or searcher.budget <= 0:
                    continue
                items, total = searcher.run_legacy(
                    skills.PlannedQuery(pq.skills, pq.terms, (pq.labels[i],), pq.legacy_terms))
                old_items, old_total = collected[id(pq)]
                collected[id(pq)] = (old_items + items, old_total + total)
        results.extend((pq, *collected[id(pq)]) for pq in pending)
    return results, searcher.log


def _balance(results, profile, pool_size):
    """Interleave results per skill so every skill gets a fair share of the
    pool. Combined queries feed every skill they serve, first."""
    found_by = {}
    raw = {}
    queues = {p["skill"]: [] for p in profile}
    ordered = sorted(results, key=lambda r: -len(r[0].skills))  # combos first
    for pq, items, _total in ordered:
        for item in items:
            if item.get("pull_request"):
                continue
            raw.setdefault(item["id"], item)
            found_by.setdefault(item["id"], set()).update(pq.skills)
            for skill in pq.skills:
                queues.setdefault(skill, []).append(item["id"])

    pool, seen = [], set()
    cursors = {skill: 0 for skill in queues}
    while len(pool) < pool_size:
        progressed = False
        for skill, queue in queues.items():
            while cursors[skill] < len(queue) and queue[cursors[skill]] in seen:
                cursors[skill] += 1
            if cursors[skill] < len(queue) and len(pool) < pool_size:
                issue_id = queue[cursors[skill]]
                seen.add(issue_id)
                issue = _normalize(raw[issue_id])
                issue["found_by"] = sorted(found_by[issue_id])
                pool.append(issue)
                progressed = True
        if not progressed:
            break
    return pool


def fetch_issues(profile, pool_size=DEFAULT_POOL):
    """Search GitHub for unassigned beginner issues across every skill in
    the profile. Returns (issues, report).

    report = {"queries": [...], "totals": {skill: total_count from GitHub},
              "mode": "advanced" | "legacy"}
    """
    profile = skills.normalise_profile(profile)
    if not profile:
        return [], {"queries": [], "totals": {}, "mode": _Searcher.mode}
    results, log = _search_all(skills.plan_queries(profile))
    totals = {}
    for pq, _items, total in results:
        if len(pq.skills) == 1:
            totals[pq.skills[0]] = totals.get(pq.skills[0], 0) + total
    pool = _balance(results, profile, pool_size)
    _attach_timeline(pool)
    return pool, {"queries": log, "totals": totals, "mode": _Searcher.mode or "advanced"}
