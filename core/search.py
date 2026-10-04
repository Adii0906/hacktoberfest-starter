"""GitHub fetch + cache.

Every raw GitHub response is cached in SQLite for 60 minutes, so reruns
during a demo never touch the API.
"""

import hashlib
import json
import os
import time

import requests

from core import db

API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"
CACHE_TTL = 60 * 60
MAX_SEARCH_QUERIES = 18  # whole search stays under 20 requests
GRAPHQL_BATCH = 20

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
    pass


def github_token():
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise GitHubError(
            "GITHUB_TOKEN is not set. Export a GitHub personal access token "
            "(public_repo read scope is enough) or switch on demo mode."
        )
    return token


def _headers():
    return {
        "Authorization": f"Bearer {github_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _wait_for_reset(resp):
    """Sleep until the rate limit window resets (capped at 60s)."""
    retry_after = resp.headers.get("retry-after")
    if retry_after:
        wait = int(retry_after)
    else:
        reset = int(resp.headers.get("x-ratelimit-reset", time.time() + 10))
        wait = reset - int(time.time()) + 1
    time.sleep(max(1, min(wait, 60)))


def _respect_remaining(resp):
    remaining = resp.headers.get("x-ratelimit-remaining")
    if remaining is not None and int(remaining) <= 1:
        _wait_for_reset(resp)


def rest_get(path, params=None):
    """Cached, rate-limit aware GET against the REST API."""
    key = "GET " + path + "?" + json.dumps(params or {}, sort_keys=True)
    cached = db.cache_get(key, CACHE_TTL)
    if cached is not None:
        return cached
    for attempt in range(2):
        resp = requests.get(API + path, headers=_headers(), params=params, timeout=30)
        if resp.status_code in (403, 429) and attempt == 0:
            _wait_for_reset(resp)
            continue
        if resp.status_code != 200:
            raise GitHubError(f"GitHub {resp.status_code} on {path}: {resp.text[:200]}")
        _respect_remaining(resp)
        body = resp.json()
        db.cache_set(key, body)
        return body
    raise GitHubError(f"GitHub rate limit on {path}")


def graphql(query, variables=None):
    """Cached, rate-limit aware GraphQL POST."""
    raw = json.dumps({"q": query, "v": variables or {}}, sort_keys=True)
    key = "GQL " + hashlib.sha256(raw.encode()).hexdigest()
    cached = db.cache_get(key, CACHE_TTL)
    if cached is not None:
        return cached
    payload = {"query": query, "variables": variables or {}}
    for attempt in range(2):
        resp = requests.post(GRAPHQL, headers=_headers(), json=payload, timeout=60)
        if resp.status_code in (403, 429) and attempt == 0:
            _wait_for_reset(resp)
            continue
        if resp.status_code != 200:
            raise GitHubError(f"GitHub GraphQL {resp.status_code}: {resp.text[:200]}")
        body = resp.json()
        if body.get("errors") and not body.get("data"):
            raise GitHubError(f"GitHub GraphQL error: {body['errors'][0].get('message')}")
        _respect_remaining(resp)
        db.cache_set(key, body)
        return body
    raise GitHubError("GitHub GraphQL rate limit")


def skill_qualifier(skill):
    skill = skill.strip().lower()
    if skill in LANGUAGES:
        return f'language:"{LANGUAGES[skill]}"'
    # Not a GitHub language: search it as a keyword instead.
    return f'"{skill}"'


def build_queries(skills):
    """One query per (skill x label) pair, label-major so every skill gets its
    best labels before any skill gets its weaker ones. Capped."""
    base = "is:issue is:open no:assignee archived:false"
    queries = []
    for label in LABEL_SYNONYMS:
        for skill in skills:
            queries.append((skill, f'{base} label:"{label}" {skill_qualifier(skill)}'))
    return queries[:MAX_SEARCH_QUERIES]


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


def fetch_issues(skills, limit=50):
    """Search GitHub for unassigned beginner issues matching the skills."""
    skills = [s.strip() for s in skills if s.strip()]
    if not skills:
        return []
    results = []  # one list per query, merged round-robin for variety
    for i, (_skill, q) in enumerate(build_queries(skills)):
        params = {"q": q, "sort": "updated", "order": "desc", "per_page": 30}
        key = "GET /search/issues?" + json.dumps(params, sort_keys=True)
        was_cached = db.cache_get(key, CACHE_TTL) is not None
        body = rest_get("/search/issues", params)
        results.append(body.get("items", []))
        if not was_cached and i + 1 < MAX_SEARCH_QUERIES:
            time.sleep(0.5)  # 30 search requests per minute, authenticated

    seen = set()
    merged = []
    depth = max((len(r) for r in results), default=0)
    for row in range(depth):
        for items in results:
            if row < len(items) and items[row]["id"] not in seen:
                seen.add(items[row]["id"])
                merged.append(_normalize(items[row]))
    merged = merged[:limit]
    _attach_timeline(merged)
    return merged
