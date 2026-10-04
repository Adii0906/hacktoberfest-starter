# hacktoberfest-starter

**Open source issues that are actually free.**

GitHub shows lots of "good first issues" that look open, but many are already
taken: someone claimed them in the comments, a pull request is already open,
or the repo is dead. This app finds beginner issues that match your skills,
throws out the taken ones, and shows you what it threw out and why.

![The reject wall](demo/reject-wall.png)

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

Open `.env` and paste your two keys after the `=` sign:

```
GITHUB_TOKEN=ghp_your_token_here
GROQ_API_KEY=gsk_your_key_here
```

| Key | Where to get it |
|---|---|
| `GITHUB_TOKEN` | https://github.com/settings/tokens, "Generate new token (classic)", no scopes needed |
| `GROQ_API_KEY` | https://console.groq.com/keys, "Create API Key" (free) |

`.env` is git-ignored, so your keys never get committed.

**3. Run**

```bash
streamlit run app.py
```

Pick your skills, choose how many hours you have, press **FIND**.

## How it works

1. **Search.** Ask GitHub for open, unassigned beginner issues in your languages.
2. **Vet.** Check what GitHub can't: claims in the comments, open pull
   requests, dead repos, repos that ban AI-written PRs.
3. **Match.** The `gpt-oss-120b` model (open-weight, run on Groq) ranks what is
   left against your skills and writes a first-hour plan and a comment you can
   post to claim the issue.

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

## Demo mode

No keys? The app starts in demo mode and replays a saved run with no network
calls. To save your own run as the demo:

```bash
python -m core.rank --skills python,sql --hours 4 --save-demo
```

## Notes

- The app never writes to GitHub. It never comments, assigns or opens PRs.
  You post the claim comment yourself.
- GitHub results are cached for 60 minutes in `starter_cache.db`.

## License

MIT, see [LICENSE](LICENSE).
