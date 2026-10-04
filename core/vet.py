"""Deterministic filters. This is the product.

GitHub says unassigned. These checks decide whether it is actually
unclaimed. Every dropped issue carries a short reason shown verbatim in
the UI. Checks run cheapest first and stop at the first failure.
"""

import re
from datetime import datetime, timezone

from core import db
from core.search import GRAPHQL_BATCH, graphql

REPO_CACHE_TTL = 6 * 60 * 60
REPO_BATCH = 5

STALE_ISSUE_DAYS = 548  # 18 months
REPO_IDLE_DAYS = 120
OUTSIDE_MERGE_DAYS = 90
FRESH_CLAIM_DAYS = 14
CROWDED_CLAIMERS = 3

AI_BAN_PATTERNS = [
    re.compile(r"\bno ai\b", re.I),
    re.compile(r"\bai-generated\b", re.I),
    re.compile(r"\bllm-generated\b", re.I),
    re.compile(r"\bno chatgpt\b", re.I),
]

CLAIM_PHRASES = [
    "can i work on",
    "can i take",
    "i'd like to work",
    "i would like to work",
    "assign me",
    "/assign",
    "please assign",
    "i'm working on",
    "im working on",
    "i'll take",
    "working on this",
    "may i",
]
# Smart quotes are common in comments typed on phones.
_QUOTES = str.maketrans({"’": "'", "‘": "'"})

HANDOFF_PATTERN = re.compile(r"\bgo ahead\b|\bassigned\b", re.I)
MAINTAINER_ROLES = {"OWNER", "MEMBER", "COLLABORATOR"}
OUTSIDE_ROLES = {"CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "NONE"}


def _parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _days_ago(ts, now):
    return (now - _parse(ts)).days


def _drop(issue, reason, category):
    return {
        "title": issue["title"],
        "url": issue["url"],
        "repo_full_name": issue["repo_full_name"],
        "reason": reason,
        "category": category,
    }


# ---------------------------------------------------------------- check 1


def _check_issue(issue, now):
    """From data already fetched: open linked PR, age."""
    open_prs = [pr for pr in issue.get("linked_prs", []) if pr["state"] == "OPEN"]
    if open_prs:
        return f"open PR #{open_prs[0]['number']} already", "open PR exists"
    age = _days_ago(issue["created_at"], now)
    if age > STALE_ISSUE_DAYS:
        return f"stale, open {age // 30} months", "stale issue"
    return None


# ---------------------------------------------------------------- check 2

_REPO_FIELDS = """
  pushedAt
  isArchived
  isFork
  owner { login }
  readme: object(expression: "HEAD:README.md") { ... on Blob { text } }
  contributing: object(expression: "HEAD:CONTRIBUTING.md") { ... on Blob { text } }
  contributingGithub: object(expression: "HEAD:.github/CONTRIBUTING.md") { ... on Blob { text } }
  contributingDocs: object(expression: "HEAD:docs/CONTRIBUTING.md") { ... on Blob { text } }
  pullRequests(states: MERGED, first: 50, orderBy: {field: UPDATED_AT, direction: DESC}) {
    nodes { mergedAt authorAssociation author { __typename login } }
  }
"""


def _summarize_repo(node):
    """Reduce a raw repository node to the facts the checks need."""
    owner = node["owner"]["login"].lower()
    outside_merges = []
    for pr in node["pullRequests"]["nodes"]:
        author = pr.get("author") or {}
        if not pr.get("mergedAt") or author.get("__typename") == "Bot":
            continue
        login = (author.get("login") or "").lower()
        if login == owner or login.endswith("[bot]"):
            continue
        if pr.get("authorAssociation") in OUTSIDE_ROLES:
            outside_merges.append(pr["mergedAt"])
    contributing = None
    for key in ("contributing", "contributingGithub", "contributingDocs"):
        if node.get(key) and node[key].get("text") is not None:
            contributing = node[key]["text"]
            break
    readme = (node.get("readme") or {}).get("text") or ""
    policy_text = readme + "\n" + (contributing or "")
    return {
        "pushed_at": node["pushedAt"],
        "archived": node["isArchived"],
        "fork": node["isFork"],
        "last_outside_merge": max(outside_merges) if outside_merges else None,
        "has_contributing": contributing is not None,
        "bans_ai": any(p.search(policy_text) for p in AI_BAN_PATTERNS),
    }


def fetch_repo_health(repos):
    """One lookup per unique repo, cached in repo_cache. Uncached repos are
    fetched a few per GraphQL request."""
    health = {}
    missing = []
    for repo in repos:
        cached = db.repo_get(repo, REPO_CACHE_TTL)
        if cached is not None:
            health[repo] = cached
        else:
            missing.append(repo)
    for start in range(0, len(missing), REPO_BATCH):
        chunk = missing[start:start + REPO_BATCH]
        parts = []
        for i, repo in enumerate(chunk):
            owner, name = repo.split("/", 1)
            parts.append(
                f'r{i}: repository(owner: "{owner}", name: "{name}") {{{_REPO_FIELDS}}}'
            )
        body = graphql("query {\n" + "\n".join(parts) + "\n}")
        data = body.get("data") or {}
        for i, repo in enumerate(chunk):
            node = data.get(f"r{i}")
            summary = _summarize_repo(node) if node else None
            if summary is not None:
                db.repo_set(repo, summary)
            health[repo] = summary
    return health


def _check_repo(repo, now):
    if repo is None:
        return "repo archived", "dead repo"  # deleted or private since indexed
    if repo["archived"] or repo["fork"]:
        return "repo archived", "dead repo"
    idle = _days_ago(repo["pushed_at"], now)
    if idle > REPO_IDLE_DAYS:
        return f"repo idle {idle // 30} months", "dead repo"
    if repo["bans_ai"]:
        return "repo bans AI PRs", "bans AI PRs"
    last = repo["last_outside_merge"]
    if last is None or _days_ago(last, now) > OUTSIDE_MERGE_DAYS:
        return "maintainers not merging", "maintainers inactive"
    return None


# ---------------------------------------------------------------- check 3

_COMMENTS_QUERY = """
query($ids: [ID!]!) {
  nodes(ids: $ids) {
    ... on Issue {
      id
      comments(last: 60) {
        nodes { createdAt body authorAssociation author { __typename login } }
      }
    }
  }
}
"""


def fetch_comments(issues):
    """A single GraphQL query per 20 issues. Never one REST call per issue."""
    comments = {}
    ids = [issue["node_id"] for issue in issues]
    for start in range(0, len(ids), GRAPHQL_BATCH):
        body = graphql(_COMMENTS_QUERY, {"ids": ids[start:start + GRAPHQL_BATCH]})
        for node in (body.get("data") or {}).get("nodes") or []:
            if node and node.get("id"):
                comments[node["id"]] = node["comments"]["nodes"]
    return comments


def _is_claim(text):
    text = text.lower().translate(_QUOTES)
    return any(phrase in text for phrase in CLAIM_PHRASES)


def classify_claims(comments, now):
    """Return (drop_reason or None, status, claim_signals)."""
    claims = []  # (login, created_at), oldest first
    handoff_to = None
    for c in comments:
        author = c.get("author") or {}
        login = author.get("login")
        if not login or author.get("__typename") == "Bot" or login.endswith("[bot]"):
            continue
        body = c.get("body") or ""
        if c.get("authorAssociation") in MAINTAINER_ROLES:
            if claims and HANDOFF_PATTERN.search(body):
                handoff_to = claims[-1][0]
            continue
        if _is_claim(body):
            claims.append((login, c["createdAt"]))

    claimers = list(dict.fromkeys(login for login, _ in claims))
    signals = {"claim_count": len(claimers)}
    if not claims:
        return None, "FREE", signals

    last_login, last_at = claims[-1]
    last_days = _days_ago(last_at, now)
    signals.update({"last_claimer": last_login, "last_claim_days": last_days})

    if last_days < FRESH_CLAIM_DAYS:
        return f"claimed by @{last_login} {last_days}d ago", None, signals
    if len(claimers) >= CROWDED_CLAIMERS:
        return f"{len(claimers)} people already asking", None, signals
    if handoff_to:
        return f"maintainer gave it to @{handoff_to}", None, signals
    # Old claim, and check 1 already proved there is no open PR.
    return None, "STALE_CLAIM", signals


# ---------------------------------------------------------------- entry


def vet(issues, now=None, on_stage=None):
    """Run all three checks. Returns (kept, dropped).

    on_stage(label, survivors) is called after each check so the UI can
    animate the funnel with real counts.
    """
    now = now or datetime.now(timezone.utc)
    dropped = []

    survivors = []
    for issue in issues:
        failure = _check_issue(issue, now)
        if failure:
            dropped.append(_drop(issue, *failure))
        else:
            survivors.append(issue)
    if on_stage:
        on_stage("checking linked pull requests", len(survivors))

    repos = list(dict.fromkeys(issue["repo_full_name"] for issue in survivors))
    health = fetch_repo_health(repos)
    passed = []
    for issue in survivors:
        repo = health.get(issue["repo_full_name"])
        failure = _check_repo(repo, now)
        if failure:
            dropped.append(_drop(issue, *failure))
            continue
        issue["repo_health"] = repo
        passed.append(issue)
    if on_stage:
        on_stage("checking repo health", len(passed))

    comments = fetch_comments(passed)
    kept = []
    for issue in passed:
        reason, status, claim_signals = classify_claims(
            comments.get(issue["node_id"], []), now
        )
        if reason:
            dropped.append(_drop(issue, reason, "already claimed"))
            continue
        repo = issue.pop("repo_health")
        last_merge = repo["last_outside_merge"]
        issue["status"] = status
        issue["warnings"] = [] if repo["has_contributing"] else ["no CONTRIBUTING.md"]
        issue["signals"] = {
            "days_since_push": _days_ago(repo["pushed_at"], now),
            "days_since_outside_merge": _days_ago(last_merge, now),
            "linked_open_prs": 0,
            "issue_age_days": _days_ago(issue["created_at"], now),
            **claim_signals,
        }
        kept.append(issue)
    if on_stage:
        on_stage("reading comments for claims", len(kept))
    return kept, dropped
