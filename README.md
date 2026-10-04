# hacktoberfest-starter

**Open source issues that are actually free.**

GitHub shows lots of "good first issues" that look open, but many are already
taken: someone claimed them in the comments, a pull request is already open,
or the repo is dead. This app finds beginner issues that match your skills,
throws out the taken ones, and shows you what it threw out and why.

## Quick start

**1. Install**

```bash
git clone https://github.com/Adii0906/hacktoberfest-starter
cd hacktoberfest-starter
pip install -r requirements.txt
```

**2. Add your keys**

```bash
cp .env.example .env
```

Open `.env` and paste your keys after the `=` sign:

```
GITHUB_TOKEN=ghp_your_token_here
GROQ_API_KEY=gsk_your_key_here
```

| Key | Needed? | Where to get it |
|---|---|---|
| `GITHUB_TOKEN` | always | https://github.com/settings/tokens, "Generate new token (classic)", no scopes needed |
| `GROQ_API_KEY` | only without a local model | https://console.groq.com/keys, "Create API Key" (free) |

**Local model or Groq?** The app picks for you on every search:

1. If [Ollama](https://ollama.com) is running on your machine with a model
   installed, the app uses that local model. No Groq key needed, nothing leaves
   your computer except the GitHub search.
2. If not, it uses `gpt-oss-120b` on Groq with your `GROQ_API_KEY`.

To use a local model:

```bash
ollama pull llama3.1      # or any chat model you like
```

Keep Ollama running and start the app. To pick a specific installed model,
set `OLLAMA_MODEL=llama3.1:8b` in `.env`. Small local models are slower and
less accurate than gpt-oss-120b, so rankings may differ.

The local path is built to stay fast on a laptop: the model gets a short
brief per issue (facts the app already checked, plus a cleaned description),
its output is held to a fixed JSON shape so it cannot break, scores are cached
for 7 days, and scoring stops after `LOCAL_TIME_BUDGET` seconds (anything not
reached is still shown, just unscored). See `.env.example` for the settings.

`.env` is git-ignored, so your keys never get committed.

**3. Run**

```bash
streamlit run app.py
```

Add your skills, set your level in each (beginner, intermediate, advanced),
choose how much time you have, press **FIND ISSUES**.

## How it works

1. **Search.** Each skill is searched the way that suits it: languages by repo
   language, frameworks, tools and topics (react, docker, sql, documentation)
   by keyword. Pairs of skills that go together get their own search too, so
   SQL work inside a Python project is found directly. Your level picks the
   labels: beginners get `good first issue` and `first-timers-only`, advanced
   contributors get `help wanted` first. Results are pooled fairly, so a skill
   with thousands of issues cannot crowd out one with forty.
2. **Verify.** Check what GitHub can't: claims in the comments, open pull
   requests, dead repos, repos that ban AI-written PRs.
3. **Match.** A language model (a local Ollama model if you have one,
   otherwise the open-weight `gpt-oss-120b` on Groq) scores what is left
   against your skills and levels, and writes a first-hour plan and a comment
   you can post to claim the issue.

Results can be filtered by skill, and a panel shows how many issues were
checked and are free for each skill, so you can see when a skill found nothing.

## How results are ranked

| Part | Weight | What it measures |
|---|---|---|
| Fit | 30% | Model: how well the work matches your skills and levels |
| Clarity | 25% | Model: how clearly the issue says what done looks like |
| Repo health | 20% | Recent pushes and recently merged outside PRs |
| Skill coverage | 15% | How many of your skills the issue uses (more is better) |
| Level fit | 10% | The level the issue needs against your level |

Issues the model has not scored are ranked by the last three alone and listed
after scored ones. The list is then re-ordered so no single skill or repo takes
every top slot.

## Why an issue gets rejected

| Rule | What you see |
|---|---|
| A pull request for it is already open | `open PR #221 already` |
| Opened more than 18 months ago | `stale, open 23 months` |
| Repo archived or a fork | `repo archived` |
| Repo not updated in 120 days | `repo idle 8 months` |
| README or CONTRIBUTING bans AI-written PRs | `repo bans AI PRs` |
| No outside contributor's PR merged in 90 days | `maintainers not merging` |
| Someone asked for it in the last 14 days | `claimed by @user 3d ago` |
| 3 or more people asked for it | `3 people already asking` |
| A maintainer already gave it to someone | `maintainer gave it to @user` |
| The model rates the issue description unclear | `too vague` |

An issue claimed more than 14 days ago with no pull request is still shown,
under **WORTH ASKING ABOUT**.

**Don't take our word for it:** every rejected issue links to the real GitHub
issue. Click one and check.

## Check the GitHub side from the terminal

```bash
python -m core.rank --skills python:advanced,sql:beginner --no-model --explain
```

This runs the search and every check without the model, prints how many
issues survive each step, every GitHub query it sent, and per-skill coverage.
Drop `--no-model` to include scoring.

## Notes

- The app never writes to GitHub. It never comments, assigns or opens PRs.
  You post the claim comment yourself.
- GitHub results are cached for 60 minutes in `starter_cache.db`, so searching
  again within the hour does not use up your GitHub rate limit. A search sends
  at most 14 requests to GitHub's search API (the limit is 30 per minute).

## License

MIT, see [LICENSE](LICENSE).
