# hacktoberfest-starter

**Open source issues that are actually free.**

GitHub search can show you every unassigned "good first issue", but unassigned
is not the same as available. Most of them are already claimed in the comments,
already have an open pull request, sit in dead repositories, or belong to
maintainers who reject AI-assisted PRs. Every other issue finder shows them
anyway, and beginners lose hours on issues they could never have landed.

hacktoberfest-starter filters those out, and shows you what it rejected and why.

![The reject wall](demo/reject-wall.png)

> Add the screenshot: run the app in demo mode, capture the right-hand
> column, and save it as `demo/reject-wall.png`.

## How it works

1. **Search.** GitHub Search API: open, unassigned issues in non-archived repos
   carrying a beginner label (`good first issue`, `good-first-issue`,
   `first-timers-only`, `help wanted`, `beginner`, `hacktoberfest`), one query per
   skill and label, capped under 20 requests. Languages become `language:`
   qualifiers; other skills (`machine learning`, `devops`) become keywords.
2. **Vet.** Deterministic checks decide what is available (table below). They
   run cheapest first and stop at the first failure.
3. **Match.** `gpt-oss-120b` reads what survived and scores fit, clarity and
   learning value against your skills, then drafts a first hour and a polite
   claim comment.

Ranking: `score = 0.40 * fit + 0.35 * clarity + 0.25 * repo health`.
Issues with an old abandoned claim are listed separately, never in the top 5.

## The vet rules

| Check | Rule | Reason shown |
|---|---|---|
| 1 | An open PR is referenced on the issue timeline | `open PR #<n> already` |
| 1 | Issue created more than 18 months ago | `stale, open <n> months` |
| 2 | Repo archived or a fork | `repo archived` |
| 2 | Repo not pushed for more than 120 days | `repo idle <n> months` |
| 2 | README or CONTRIBUTING contains "no AI", "AI-generated", "LLM-generated" or "no ChatGPT" | `repo bans AI PRs` |
| 2 | No PR from an outside contributor merged in 90 days | `maintainers not merging` |
| 2 | No CONTRIBUTING.md | warning only, not dropped |
| 3 | A claim comment in the last 14 days | `claimed by @user <n>d ago` |
| 3 | 3 or more different people asking for it | `<n> people already asking` |
| 3 | A maintainer replied "go ahead" or "assigned" to a claimer | `maintainer gave it to @user` |
| 3 | Claim older than 14 days and no PR | kept, marked STALE CLAIM |
| 3 | No claim at all | kept, marked FREE |
| model | Clarity below 4 / 10 | `too vague` |

Claim phrases (case insensitive): "can i work on", "can i take",
"i'd like to work", "i would like to work", "assign me", "/assign",
"please assign", "i'm working on", "im working on", "i'll take",
"working on this", "may i". Bots are ignored.

Comments are read with one GraphQL query per 20 issues, never one REST call per
issue. Every GitHub response is cached in `starter_cache.db` for 60 minutes.

## Setup

Python 3.11.

```bash
pip install -r requirements.txt
export GITHUB_TOKEN=ghp_...     # any personal access token with public read access
export GROQ_API_KEY=gsk_...     # from console.groq.com
streamlit run app.py
```

Without `GITHUB_TOKEN` the app starts in demo mode, which replays
`demo/cached_run.json` and makes zero network calls. To record your own demo
from a real run:

```bash
python -m core.rank --skills python,sql --hours 4 --save-demo
```

## The model

Matching uses `openai/gpt-oss-120b`, an open-weight model, served through
[Groq](https://groq.com). Issue bodies are treated as untrusted data: they are
wrapped in delimiters, the model is told to ignore instructions inside them,
the call has no tools, and output is forced to JSON and schema-checked. An
issue the model fails on twice is shown as unjudged rather than crashing.

Deterministic filters decide what is available. The model only decides what
fits you. Both are shown, neither is hidden.

## Verify it yourself

Every rejected issue on the wall links to the real GitHub issue. Click any of
them and check: the claim comment, the open PR, the last push date. The wall is
the point. It is what every other tool would have handed you.

The app never writes to GitHub. It does not comment, assign or open PRs.
We never post. You do.

## License

MIT, see [LICENSE](LICENSE).
