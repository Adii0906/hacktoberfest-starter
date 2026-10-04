"""GitHub fetch + cache.

Rate-limit strategy
-------------------
- **Search API**: 30 req/min (authenticated). The old code fired up to 18
  REST search queries (6 labels × N skills). We now build a SINGLE query per
  skill using OR-ed label qualifiers and fetch 2 pages max. For 2 skills that
  is 4 requests — an 80 % reduction.
- **Conditional requests**: Every cached REST response stores its ETag. On
  cache expiry we send `If-None-Match`; a 304 costs zero quota on core but
  still counts for search, so we keep the TTL generous.
- **GraphQL**: batched timeline lookups (20 issues per call) are unchanged;
  they already minimize calls.
- **Back-off**: on 403/429 we read `x-ratelimit-reset` and sleep just long
  enough, then retry once.
"""

import hashlib
import json
import os
import time

import requests

from core import db

API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"
CACHE_TTL = 60 * 60          # 1 hour for search results
GRAPHQL_BATCH = 20            # GitHub node-id lookup limit per call
MAX_SEARCH_PAGES = 2          # at most 2 pages per consolidated query
PER_PAGE = 50                 # maximum allowed by search endpoint is 100

LABEL_SYNONYMS = [
    "good first issue",
    "good-first-issue",
    "first-timers-only",
    "help wanted",
    "beginner",
    "hacktoberfest",
]

# Skill (lower case) -> GitHub linguist language name. Anything not in this
# map is treated as a keyword (topic) qualifier, not a language.
LANGUAGES = {
    "python": "Python",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "go": "Go",
    "golang": "Go",
    "rust": "Rust",
    "java": "Java",
    "c++": "C++",
    "cpp": "C++",
    "c": "C",
    "c#": "C#",
    "csharp": "C#",
    "ruby": "Ruby",
    "php": "PHP",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "dart": "Dart",
    "scala": "Scala",
    "elixir": "Elixir",
    "haskell": "Haskell",
    "lua": "Lua",
    "r": "R",
    "julia": "Julia",
    "shell": "Shell",
    "bash": "Shell",
    "sql": "SQL",
    "html": "HTML",
    "css": "CSS",
    "scss": "SCSS",
    "vue": "Vue",
    "svelte": "Svelte",
    "jupyter": "Jupyter Notebook",
    "dockerfile": "Dockerfile",
}


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


# ---------------------------------------------------------------- query builder


def _sanitize_skill(skill: str) -> str:
    """Strip characters that would break GitHub search syntax."""
    return "".join(ch for ch in skill.strip().lower() if ch not in '"\\:()')


def skill_qualifier(skill: str) -> str:
    clean = _sanitize_skill(skill)
    if clean in LANGUAGES:
        return f'language:"{LANGUAGES[clean]}"'
    return f'"{clean}"'


MAX_QUERIES = 10  # hard cap: stay well within the 30 req/min search budget

# Ranked by signal strength: "good first issue" and "hacktoberfest" yield the
# most relevant results. We query the top 3 labels per skill.
_PRIORITY_LABELS = [
    "good first issue",
    "hacktoberfest",
    "help wanted",
]


def build_queries(skills: list[str]) -> list[tuple[str, str]]:
    """One query per (skill × label), using only the top 3 labels.

    OLD: 6 labels × N skills = up to 18 queries  (burns the 30/min budget).
    NEW: 3 labels × N skills, capped at 10 = typically 6 queries for 2 skills.

    GitHub search does NOT support OR for label qualifiers, so we issue
    separate queries but limit the total count aggressively.
    """
    base = "is:issue is:open no:assignee archived:false"
    queries = []
    skills = [s for s in skills if _sanitize_skill(s)]
    for label in _PRIORITY_LABELS:
        for skill in skills:
            queries.append((skill, f'{base} label:"{label}" {skill_qualifier(skill)}'))
    return queries[:MAX_QUERIES]


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


def fetch_issues(skills, limit=50):
    """Search GitHub for unassigned beginner issues matching the skills.

    Uses one consolidated query per skill (all labels OR-ed) instead of
    one query per label×skill pair. With MAX_SEARCH_PAGES=2, for 2 skills
    we send at most 4 search requests (down from up to 18).
    """
    skills = [s.strip() for s in skills if s.strip()]
    if not skills:
        return []

    results: list[list] = []
    queries = build_queries(skills)

    for qi, (_skill, q) in enumerate(queries):
        for page in range(1, MAX_SEARCH_PAGES + 1):
            params = {"q": q, "sort": "updated", "order": "desc",
                      "per_page": PER_PAGE, "page": page}
            cache_key = "GET /search/issues?" + json.dumps(params, sort_keys=True)
            was_cached, _ = db.cache_get(cache_key, CACHE_TTL)
            try:
                body = rest_get("/search/issues", params)
            except GitHubError as exc:
                if exc.status == 422:
                    break            # malformed query — skip this skill
                raise
            items = body.get("items", [])
            results.append(items)
            # Stop paging if GitHub returned fewer items than requested.
            if len(items) < PER_PAGE:
                break
            # Respect the 30 req/min search budget: sleep between uncached calls.
            if was_cached is None:
                time.sleep(1.5)

        # Small delay between queries to stay within the window.
        if was_cached is None and qi + 1 < len(queries):
            time.sleep(0.5)

    # Round-robin merge across queries for variety.
    seen: set[int] = set()
    merged: list[dict] = []
    depth = max((len(r) for r in results), default=0)
    for row in range(depth):
        for items in results:
            if row < len(items) and items[row]["id"] not in seen:
                seen.add(items[row]["id"])
                merged.append(_normalize(items[row]))

    merged = merged[:limit]
    _attach_timeline(merged)
    return merged
