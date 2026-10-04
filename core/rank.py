"""Scoring, diversified ranking, and the full search -> vet -> judge -> rank run.

Score (0-10)
------------
Scored issues (read by the model):
    0.30 fit + 0.25 clarity + 0.20 repo health + 0.15 skill coverage + 0.10 level fit
Unscored issues (deterministic signals only, always listed after scored ones):
    0.45 repo health + 0.35 skill coverage + 0.20 level fit

- repo health: half recency of the last push, half recency of the last
  merged PR from an outside contributor.
- skill coverage: 6 for one strong skill match, +3 for each further strong
  match, +1.5 for each weak match, 3 if every match is weak. Issues that use
  several of your skills rank higher.
- level fit: the level the issue needs against your level in the skills it
  uses. A beginner pointed at an advanced issue scores low.

Diversity: the ordered list is re-ranked so one skill or one repo cannot take
every top slot. Each pick is penalised by how many already-picked issues share
its least-represented matching skill (1 point each) or its repo (1.5 each).

Run it without the UI to check the live GitHub side:
    python -m core.rank --skills python:advanced,sql:beginner --no-model --explain
"""

import argparse
import time

from core import db, judge, search, skills, vet

TOP_STALE = 3
VAGUE_CLARITY = 4  # clarity below this is dropped as "too vague"
SKILL_PENALTY = 1.0
REPO_PENALTY = 1.5

_RANK = {level: i for i, level in enumerate(skills.LEVELS)}
# (your level, level the issue needs) -> 0-10
LEVEL_FIT = {
    ("beginner", "beginner"): 10, ("beginner", "intermediate"): 5, ("beginner", "advanced"): 1,
    ("intermediate", "beginner"): 8, ("intermediate", "intermediate"): 10, ("intermediate", "advanced"): 5,
    ("advanced", "beginner"): 6, ("advanced", "intermediate"): 9, ("advanced", "advanced"): 10,
}


def health_score(signals):
    """0-10. Half repo recency (0 at 120 idle days), half outside-merge
    activity (0 at 90 days since an outside PR was merged)."""
    push = max(0.0, 10 - signals["days_since_push"] / (vet.REPO_IDLE_DAYS / 10))
    merge = max(0.0, 10 - signals["days_since_outside_merge"] / (vet.OUTSIDE_MERGE_DAYS / 10))
    return round(0.5 * push + 0.5 * merge, 1)


def coverage_score(matches):
    strong = sum(1 for m in matches if m["strength"] == "strong")
    weak = len(matches) - strong
    if strong == 0:
        return 3.0 if weak else 0.0
    return min(10.0, 6 + 3 * (strong - 1) + 1.5 * weak)


def working_level(matches):
    """Your level in the skills this issue leans on: the highest level among
    strong matches, else among all matches."""
    pool = [m for m in matches if m["strength"] == "strong"] or matches
    if not pool:
        return skills.DEFAULT_LEVEL
    return max((m["level"] for m in pool), key=_RANK.get)


def level_fit(issue):
    needed = (issue.get("judgment") or {}).get("difficulty") or issue.get("label_difficulty")
    if needed is None:
        return 7.0
    return float(LEVEL_FIT[(working_level(issue["matches"]), needed)])


def score(issue):
    h, c, lv = issue["health_score"], issue["coverage_score"], level_fit(issue)
    j = issue.get("judgment")
    if not j:
        return round(0.45 * h + 0.35 * c + 0.20 * lv, 2)
    return round(0.30 * j["fit"] + 0.25 * j["clarity"] + 0.20 * h + 0.15 * c + 0.10 * lv, 2)


def diversify(items):
    """Greedy re-rank: best adjusted score first, where the adjustment
    penalises skills and repos already well represented above."""
    remaining = sorted(items, key=lambda i: i["score"], reverse=True)
    skill_count, repo_count, out = {}, {}, []
    while remaining:
        def adjusted(issue):
            keys = [m["skill"] for m in issue["matches"]] or ["?"]
            skill_pen = min(skill_count.get(k, 0) for k in keys)
            return issue["score"] - SKILL_PENALTY * skill_pen - REPO_PENALTY * repo_count.get(issue["repo_full_name"], 0)
        best = max(remaining, key=adjusted)
        remaining.remove(best)
        out.append(best)
        for m in best["matches"]:
            skill_count[m["skill"]] = skill_count.get(m["skill"], 0) + 1
        repo_count[best["repo_full_name"]] = repo_count.get(best["repo_full_name"], 0) + 1
    return out


def annotate(kept, profile):
    """Deterministic fields every kept issue needs before ranking."""
    for issue in kept:
        issue["matches"] = skills.match_skills(issue, profile)
        issue["label_difficulty"] = skills.difficulty_from_labels(issue.get("labels", []))
        issue["health_score"] = health_score(issue["signals"])
        issue["coverage_score"] = coverage_score(issue["matches"])
        issue["judgment"] = None
        issue["score"] = score(issue)


def judge_candidates(kept, limit):
    """Which issues the model reads, chosen by the deterministic score and
    diversified so every skill gets its share of the model's time."""
    free = diversify([i for i in kept if i["status"] == "FREE"])
    stale = diversify([i for i in kept if i["status"] == "STALE_CLAIM"])
    n_stale = min(len(stale), 2, max(0, limit // 4))
    return free[:limit - n_stale] + stale[:n_stale]


def rank(kept, judgments):
    """Returns {"free", "stale", "rollup", "vague"}. STALE_CLAIM issues are
    ranked separately and never mixed into the free list."""
    free, stale, vague = [], [], []
    for issue in kept:
        issue["judgment"] = judgments.get(issue["id"])
        issue["judged"] = issue["judgment"] is not None
        if issue["judged"] and issue["judgment"]["clarity"] < VAGUE_CLARITY:
            vague.append(vet._drop(issue, "too vague", "too vague"))
            continue
        issue["score"] = score(issue)
        (free if issue["status"] == "FREE" else stale).append(issue)

    def ordered(items):
        return (diversify([i for i in items if i["judged"]])
                + diversify([i for i in items if not i["judged"]]))

    rollup = {}
    for issue in free:
        rollup[issue["repo_full_name"]] = rollup.get(issue["repo_full_name"], 0) + 1
    return {"free": ordered(free), "stale": ordered(stale)[:TOP_STALE], "rollup": rollup, "vague": vague}


def coverage_report(profile, pool, free, totals):
    """Per skill: GitHub's total, how many reached the pool, how many are free."""
    rows = []
    for p in profile:
        key = p["skill"]
        rows.append({
            "skill": key,
            "level": p["level"],
            "kind": skills.KINDS[skills.lookup(key).kind],
            "github_total": totals.get(key, 0),
            "found": sum(1 for i in pool if key in i.get("found_by", [])),
            "free": sum(1 for i in free if any(m["skill"] == key for m in i["matches"])),
        })
    return rows


def _slim(issue):
    """Drop fields the UI never shows, to keep session state small."""
    return {k: v for k, v in issue.items() if k not in ("body", "node_id")}


def run(profile, hours, on_stage=None, on_progress=None, use_model=True):
    """Full pipeline. on_stage(label, count) fires after every stage with the
    real surviving count; on_progress(done, total) during model scoring."""
    def stage(label, count):
        funnel.append({"label": label, "count": count})
        if on_stage:
            on_stage(label, count)

    profile = skills.normalise_profile(profile)
    funnel = []
    pool, report = search.fetch_issues(profile)
    stage(f"searching GitHub for {', '.join(p['skill'] for p in profile)}", len(pool))

    kept, dropped = vet.vet(pool, on_stage=stage)
    annotate(kept, profile)

    judgments, backend = {}, None
    if use_model and kept:
        backend = judge._client()
        candidates = judge_candidates(kept, backend.max_judged)
        judgments = judge.judge_many(
            candidates, {"skills": profile, "hours": hours}, client=backend, on_progress=on_progress)
    ranked = rank(kept, judgments)
    dropped.extend(ranked["vague"])
    stage("matching against your skills", len(ranked["free"]))

    payload = {
        "created_at": int(time.time()),
        "profile": profile,
        "skills": [p["skill"] for p in profile],
        "hours": hours,
        "model": f"{backend.name}:{backend.model}" if backend else None,
        "scanned": len(pool),
        "scored": sum(1 for v in judgments.values() if v is not None),
        "funnel": funnel,
        "free": [_slim(i) for i in ranked["free"]],
        "stale": [_slim(i) for i in ranked["stale"]],
        "rollup": ranked["rollup"],
        "dropped": dropped,
        "coverage": coverage_report(profile, pool, ranked["free"], report["totals"]),
        "search": report,
    }
    db.save_run(payload)
    return payload


def main():
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(description="Run the pipeline from the command line.")
    parser.add_argument("--skills", required=True,
                        help="comma separated skill[:level], e.g. python:advanced,sql:beginner")
    parser.add_argument("--hours", default="4")
    parser.add_argument("--no-model", action="store_true", help="skip model scoring, GitHub checks only")
    parser.add_argument("--explain", action="store_true", help="print every search query and per-skill coverage")
    args = parser.parse_args()
    profile = skills.parse_cli_profile(args.skills)

    def show(label, count):
        print(f"  {label:<52}{count:>4}")

    def progress(done, total):
        print(f"  scoring {done}/{total}", end="\r", flush=True)

    print(f"SCANNING  {skills.describe(profile)}")
    payload = run(profile, args.hours, on_stage=show, on_progress=progress, use_model=not args.no_model)
    if payload["model"]:
        print(f"  scored {payload['scored']} issues with {payload['model']}")
    if args.explain:
        print(f"\nSEARCH MODE  {payload['search']['mode']}")
        for q in payload["search"]["queries"]:
            print(f"  [{'+'.join(q['skills'])}] returned {q['returned']:>3} of {q['total']:>6}  {q['query']}")
        print("\nCOVERAGE  skill (level): on GitHub / in pool / free")
        for row in payload["coverage"]:
            print(f"  {row['skill']} ({row['level']}): {row['github_total']} / {row['found']} / {row['free']}")
    print(f"\n{len(payload['free'])} issues you can actually take.")
    print(f"{len(payload['dropped'])} you would have wasted time on.")
    for issue in payload["free"][:10]:
        tags = ", ".join(m["skill"] for m in issue["matches"])
        print(f"  {issue['score']:>5}  [{tags}]  {issue['title'][:70]}  {issue['url']}")


if __name__ == "__main__":
    main()
