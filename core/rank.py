"""Scoring, plus the full search -> vet -> judge -> rank run.

Save a real run for the offline demo:
    python -m core.rank --skills python,sql --hours 4 --save-demo
"""

import argparse
import json
import os
import time

from core import db, judge, search, vet

TOP_FREE = 5
TOP_STALE = 3
MAX_JUDGED = 20
VAGUE_CLARITY = 4  # clarity below this is dropped as "too vague"
DEMO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "demo", "cached_run.json")


def health_score(signals):
    """0-10. Half repo recency (0 at 120 idle days), half outside-merge
    activity (0 at 90 days since an outside PR was merged)."""
    push = max(0.0, 10 - signals["days_since_push"] / (vet.REPO_IDLE_DAYS / 10))
    merge = max(0.0, 10 - signals["days_since_outside_merge"] / (vet.OUTSIDE_MERGE_DAYS / 10))
    return round(0.5 * push + 0.5 * merge, 1)


def score(issue):
    j = issue.get("judgment")
    h = issue["health_score"]
    if not j:
        return 0.25 * h  # unjudged sorts below every judged issue of equal health
    return round(0.40 * j["fit"] + 0.35 * j["clarity"] + 0.25 * h, 2)


def rank(kept, judgments):
    """Returns {"top", "stale", "rollup", "vague"}.

    STALE_CLAIM issues are ranked separately and never enter the top 5.
    """
    free, stale, vague = [], [], []
    for issue in kept:
        issue["health_score"] = health_score(issue["signals"])
        issue["judgment"] = judgments.get(issue["id"])
        issue["judged"] = issue["judgment"] is not None
        if issue["judged"] and issue["judgment"]["clarity"] < VAGUE_CLARITY:
            vague.append(vet._drop(issue, "too vague", "too vague"))
            continue
        issue["score"] = score(issue)
        (free if issue["status"] == "FREE" else stale).append(issue)

    def order(items):
        return sorted(items, key=lambda i: (i["judged"], i["score"]), reverse=True)

    rollup = {}
    for issue in free:
        rollup[issue["repo_full_name"]] = rollup.get(issue["repo_full_name"], 0) + 1
    return {
        "top": order(free)[:TOP_FREE],
        "stale": order(stale)[:TOP_STALE],
        "rollup": rollup,
        "vague": vague,
    }


def _judge_candidates(kept):
    """Bound model latency: judge the healthiest issues only."""
    def health(i):
        return health_score(i["signals"])
    free = sorted((i for i in kept if i["status"] == "FREE"), key=health, reverse=True)
    stale = sorted((i for i in kept if i["status"] == "STALE_CLAIM"), key=health, reverse=True)
    return free[:MAX_JUDGED - TOP_STALE] + stale[:TOP_STALE]


def run(skills, hours, on_stage=None, use_model=True):
    """Full pipeline. on_stage(label, count) fires after every stage with
    the real surviving count, so the UI funnel shows true numbers."""
    def stage(label, count):
        funnel.append({"label": label, "count": count})
        if on_stage:
            on_stage(label, count)

    funnel = []
    issues = search.fetch_issues(skills, limit=50)
    stage(f"fetching issues for {', '.join(skills)}", len(issues))

    kept, dropped = vet.vet(issues, on_stage=stage)

    judgments = {}
    if use_model and kept:
        profile = {"skills": skills, "hours": hours}
        judgments = judge.judge_many(_judge_candidates(kept), profile)
    ranked = rank(kept, judgments)
    dropped.extend(ranked["vague"])
    stage("matching against your skills", len(ranked["top"]))

    payload = {
        "created_at": int(time.time()),
        "skills": skills,
        "hours": hours,
        "model": judge.MODEL,
        "scanned": len(issues),
        "funnel": funnel,
        "top": ranked["top"],
        "stale": ranked["stale"],
        "rollup": ranked["rollup"],
        "dropped": dropped,
    }
    db.save_run(payload)
    return payload


def main():
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(description="Run the pipeline from the command line.")
    parser.add_argument("--skills", required=True, help="comma separated, e.g. python,sql")
    parser.add_argument("--hours", default="4")
    parser.add_argument("--save-demo", action="store_true", help=f"write {DEMO_PATH}")
    parser.add_argument("--no-model", action="store_true", help="skip the Groq judge")
    args = parser.parse_args()
    skills = [s.strip().lower() for s in args.skills.split(",") if s.strip()]

    def show(label, count):
        print(f"  {label:<45}{count:>4}")

    print("SCANNING")
    payload = run(skills, args.hours, on_stage=show, use_model=not args.no_model)
    print(f"\n{len(payload['top'])} issues you can actually take.")
    print(f"{len(payload['dropped'])} you would have wasted time on.")
    if args.save_demo:
        with open(DEMO_PATH, "w") as f:
            json.dump(payload, f, indent=1)
        print(f"saved {DEMO_PATH}")


if __name__ == "__main__":
    main()
