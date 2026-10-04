"""HACKTOBERFEST STARTER. GitHub says unassigned. We check if it is actually unclaimed."""

import html
import time

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # reads GITHUB_TOKEN and GROQ_API_KEY from .env

from core import judge, rank, search, skills  # noqa: E402

st.set_page_config(
    page_title="HACKTOBERFEST STARTER",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Palette, all checked against the #0D1117 background:
#   #E6EDF3 text 16:1, #C9D1D9 text 12:1, #9DA7B3 muted 7.5:1,
#   #3FB950 green 7.8:1, #FF7B72 red 7.0:1, #E3B341 amber 10:1.
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');
#MainMenu, footer, header, [data-testid="stHeader"], [data-testid="stToolbar"] {
  visibility: hidden; height: 0;
}
html, body, .stApp, .stApp *:not([data-testid="stIconMaterial"]):not(.material-symbols-rounded) {
  font-family: "JetBrains Mono", "SF Mono", monospace !important;
}
.block-container { padding-top: 2rem; padding-bottom: 5rem; }
.pill {
  display: inline-block; padding: 2px 10px; border-radius: 999px; margin-right: 6px;
  font-size: 11px; letter-spacing: 1px; text-transform: uppercase; font-weight: 700;
}
.pill.free { color: #3FB950; border: 1px solid #3FB950; }
.pill.stale { color: #E3B341; border: 1px solid #E3B341; }
.muted { color: #9DA7B3; }
.small { font-size: 13px; }
.label { color: #9DA7B3; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; margin: 16px 0 6px; }
.rule { border: 0; border-top: 1px solid #30363D; margin: 36px 0; }
.page, .st-key-profile_form, .st-key-empty_actions { max-width: 860px; margin: 0 auto; width: 100%; }

.eyebrow { color: #3FB950; font-size: 13px; letter-spacing: 3px; margin-top: 2.5rem; }
.hero h1 { font-size: 44px; color: #E6EDF3; margin: 14px 0 0; line-height: 1.15; letter-spacing: -0.5px; }
.hero .sub { color: #C9D1D9; font-size: 17px; margin-top: 18px; line-height: 1.65; }
.hero .tag { color: #9DA7B3; font-size: 14px; margin-top: 18px; }
.section-title { color: #9DA7B3; font-size: 13px; letter-spacing: 3px; margin-bottom: 14px; }
.step { display: flex; gap: 28px; padding: 16px 0; align-items: baseline; }
.step + .step { border-top: 1px solid #21262D; }
.step .name { flex: 0 0 120px; font-size: 14px; font-weight: 700; letter-spacing: 2px; color: #9DA7B3; }
.step .text { font-size: 15px; line-height: 1.6; color: #C9D1D9; }
.step.key .name { color: #3FB950; font-size: 20px; }
.step.key .text { color: #E6EDF3; font-size: 17px; font-weight: 600; }
.rules { display: grid; grid-template-columns: 1fr 1fr; gap: 0 32px; }
.rules div { padding: 9px 0; border-bottom: 1px solid #21262D; font-size: 14px; line-height: 1.5; color: #C9D1D9; }
.rules .reason { color: #FF7B72; }
.gets { margin: 0; padding-left: 22px; color: #C9D1D9; font-size: 15px; line-height: 1.9; }
@media (max-width: 720px) {
  .rules { grid-template-columns: 1fr; }
  .rules .reason { border-bottom-width: 2px; }
  .step { flex-direction: column; gap: 4px; }
  .hero h1 { font-size: 32px; }
}

.form-step { color: #E6EDF3; font-size: 15px; font-weight: 700; margin: 18px 0 4px; }
.form-hint { color: #9DA7B3; font-size: 13px; margin-bottom: 8px; line-height: 1.5; }
.skill-name { color: #E6EDF3; font-size: 15px; padding-top: 6px; }
.kind { color: #9DA7B3; font-size: 11px; letter-spacing: 1px; text-transform: uppercase; margin-left: 8px; }
.plan { color: #9DA7B3; font-size: 13px; margin-top: 10px; line-height: 1.6; }
.plan b { color: #C9D1D9; font-weight: 600; }

.chip {
  display: inline-block; padding: 3px 10px; margin: 0 6px 6px 0; border-radius: 999px;
  border: 1px solid #30363D; background: #161B22; font-size: 13px; color: #E6EDF3;
}
.chip .muted { font-size: 11px; }
.match {
  display: inline-block; padding: 1px 8px; margin: 0 6px 4px 0; border-radius: 4px;
  font-size: 12px; color: #3FB950; border: 1px solid #2EA04366;
}
.match.weak { color: #9DA7B3; border: 1px dashed #30363D; }
.err {
  border-left: 3px solid #FF7B72; padding: 8px 14px; color: #FF7B72;
  font-size: 14px; margin: 12px 0; line-height: 1.5;
}
.note { border-left: 3px solid #E3B341; padding: 6px 12px; color: #C9D1D9; font-size: 13px; margin: 0 0 14px; line-height: 1.5; }

.funnel { max-width: 720px; margin: 4rem auto 0; }
.funnel h2 { letter-spacing: 6px; font-size: 20px; margin-bottom: 1.5rem; color: #E6EDF3; }
.frow { margin: 0 0 16px; }
.frow .top { display: flex; justify-content: space-between; gap: 16px; font-size: 15px; color: #C9D1D9; }
.frow .bar-bg { background: #21262D; height: 8px; border-radius: 4px; margin-top: 6px; }
.frow .bar { background: #3FB950; height: 8px; border-radius: 4px; }
.frow.pending .top { color: #9DA7B3; }
.done-green { color: #3FB950; font-size: 20px; font-weight: 700; margin-top: 1.5rem; }
.done-grey { color: #C9D1D9; font-size: 16px; margin-top: 4px; }

.issue-title { margin-top: 10px; line-height: 1.4; }
.issue-title a { font-size: 16px; font-weight: 700; color: #E6EDF3; text-decoration: none; }
.issue-title a:hover { color: #3FB950; text-decoration: underline; }
.meta { color: #9DA7B3; font-size: 13px; margin-top: 4px; overflow-wrap: anywhere; }
.thin { border: 0; border-top: 1px solid #30363D; margin: 12px 0; }
.body-text { font-size: 14px; line-height: 1.6; color: #C9D1D9; }
.stats { display: flex; flex-wrap: wrap; gap: 28px; margin: 14px 0 4px; }
.stats div { font-size: 12px; color: #9DA7B3; }
.stats b { color: #E6EDF3; font-size: 16px; display: block; }
ol.steps-list, ul.steps-list { padding-left: 22px; margin: 0; font-size: 14px; line-height: 1.6; color: #C9D1D9; }
.rollup { color: #3FB950; font-size: 13px; margin: 10px 0; }

.summary-row { display: flex; justify-content: space-between; gap: 12px; font-size: 14px; padding: 3px 0; color: #9DA7B3; }
.summary-row b { color: #E6EDF3; text-align: right; overflow-wrap: anywhere; }
.cov { padding: 8px 0; border-bottom: 1px solid #21262D; }
.cov .head { color: #E6EDF3; font-size: 14px; }
.cov .nums { color: #9DA7B3; font-size: 12px; margin-top: 2px; }
.cov .nums b { color: #C9D1D9; }
.cov .warn { color: #E3B341; font-size: 12px; margin-top: 2px; }

.wall { border-left: 3px solid #FF7B72; padding: 2px 0 2px 20px; }
.wall h3 { color: #FF7B72; font-size: 16px; letter-spacing: 2px; margin: 0; line-height: 1.4; }
.wall .sub { color: #C9D1D9; font-size: 14px; margin: 6px 0 16px; }
.wall-row { padding: 8px 0; border-bottom: 1px solid #21262D; line-height: 1.45; }
.wall-row a.reject {
  color: #C9D1D9; font-size: 14px; text-decoration: line-through;
  text-decoration-color: #FF7B72; text-decoration-thickness: 1px; overflow-wrap: anywhere;
}
.wall-row a.reject:hover { color: #E6EDF3; }
.wall-row .why { display: block; color: #FF7B72; font-size: 13px; margin-top: 2px; }

div[data-testid="stColumn"]:has(.sticky-marker), div[data-testid="column"]:has(.sticky-marker) {
  position: sticky; top: 2rem; align-self: flex-start;
}
[class*="st-key-rf_"] button {
  background: transparent; border: none; padding: 2px 0; min-height: 0;
  justify-content: flex-start; color: #C9D1D9;
}
[class*="st-key-rf_"] button:hover { color: #FF7B72; background: transparent; }
[class*="st-key-rf_"] button p { font-size: 14px; }

.app-footer {
  position: fixed; left: 0; right: 0; bottom: 0; padding: 8px 16px; text-align: center;
  font-size: 12px; color: #9DA7B3; background: #0D1117; border-top: 1px solid #21262D; z-index: 100;
}
</style>
""",
    unsafe_allow_html=True,
)

HOURS = ["2", "4", "8", "a weekend"]
LEVEL_HINT = ("Beginner: still learning it. Intermediate: you have built something with it. "
              "Advanced: comfortable in a large codebase.")
CATEGORIES = [
    "already claimed", "open PR exists", "dead repo", "stale issue",
    "maintainers inactive", "bans AI PRs", "too vague",
]
ALL = "__all__"
PAGE = 5
NBSP = " "
DEFAULT_PROFILE = [{"skill": "python", "level": "intermediate"}, {"skill": "sql", "level": "beginner"}]

for key, default in {
    "screen": "landing",
    "result": None,
    "query": None,
    "error": None,
    "reject_filter": None,
    "profile": None,
    "hours_saved": "4",
    "shown": PAGE,
    "filter_prev": ALL,
}.items():
    st.session_state.setdefault(key, default)


def esc(text):
    return html.escape(str(text), quote=True)


def md(markup):
    st.markdown(markup, unsafe_allow_html=True)


def error_box(message):
    md(f'<div class="err">{esc(message)}</div>')


def ago(days):
    if days is None:
        return "never"
    if days <= 0:
        return "today"
    return f"{days} day{'s' if days != 1 else ''} ago"


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def level_key(skill):
    return "lvl_" + skill.encode().hex()


def footer():
    md(
        '<div class="app-footer">Fixed rules decide what is available. '
        "Ranking decides what fits you. Both are shown, nothing is hidden.</div>"
    )


# ---------------------------------------------------------------- screen 1


def render_hero():
    md(
        '<div class="page hero">'
        '<div class="eyebrow">HACKTOBERFEST STARTER</div>'
        "<h1>Open source issues that are actually free.</h1>"
        '<div class="sub">GitHub calls an issue open as long as nobody is assigned. Many of those are '
        "already claimed in the comments, already have a pull request, or sit in repos nobody maintains. "
        "We check all of that for you, then match what is left to your skills and your level in each.</div>"
        '<div class="tag">GitHub says unassigned. We check if it is actually unclaimed.</div>'
        "</div>"
        '<div class="page"><hr class="rule">'
        '<div class="section-title">HOW IT WORKS</div>'
        '<div class="step"><div class="name">SEARCH</div>'
        '<div class="text">We search GitHub for beginner-labelled issues in every skill you add, and '
        "for issues that need two of your skills at once, like SQL work inside a Python project.</div></div>"
        '<div class="step key"><div class="name">VERIFY</div>'
        '<div class="text">We check what GitHub cannot: who already claimed it in the comments, open PRs, '
        "dead repos, maintainers who ban AI PRs.</div></div>"
        '<div class="step"><div class="name">MATCH</div>'
        '<div class="text">We rank what survives against your skills, your level in each and the time you '
        "have, and keep every skill represented in the results.</div></div>"
        '<hr class="rule"></div>'
    )


def render_explainer():
    rules = [
        ("Someone asked for it in the last 14 days", "claimed by @user 3d ago"),
        ("A maintainer already gave it to someone", "maintainer gave it to @user"),
        ("Three or more people asked for it", "3 people already asking"),
        ("A pull request for it is already open", "open PR #221 already"),
        ("Repo not updated in 120 days", "repo idle 8 months"),
        ("No outside contributor's PR merged in 90 days", "maintainers not merging"),
        ("Repo archived or a fork", "repo archived"),
        ("README or CONTRIBUTING bans AI-written PRs", "repo bans AI PRs"),
        ("The description does not say what done looks like", "too vague"),
    ]
    cells = "".join(f"<div>{esc(rule)}</div><div class=\"reason\">{esc(reason)}</div>" for rule, reason in rules)
    md(
        '<div class="page"><hr class="rule">'
        '<div class="section-title">WHAT WE CATCH, AND WHAT YOU SEE</div>'
        f'<div class="rules">{cells}</div>'
        '<div class="form-hint" style="margin-top:12px">Every rejected issue links to the real issue on '
        "GitHub, so you can check it yourself.</div>"
        '<hr class="rule">'
        '<div class="section-title">WHAT YOU GET FOR EACH ISSUE</div>'
        '<ul class="gets">'
        "<li>Which of your skills it needs, and whether it suits your level</li>"
        "<li>Fit, clarity and an estimate of the hours</li>"
        "<li>Three concrete steps for your first hour</li>"
        "<li>A short comment to ask the maintainer for it. We never post. You do.</li>"
        "</ul></div>"
    )


def _init_profile_widgets():
    """Seed widget state from the saved profile. Streamlit drops widget state
    for widgets not drawn in a run, so the profile lives in its own key."""
    saved = st.session_state.profile or DEFAULT_PROFILE
    if "skills_ms" not in st.session_state:
        st.session_state.skills_ms = [p["skill"] for p in saved]
    for p in saved:
        st.session_state.setdefault(level_key(p["skill"]), p["level"])
    st.session_state.setdefault("hours_sel", st.session_state.hours_saved)


def render_profile_form():
    _init_profile_widgets()
    with st.container(key="profile_form"):
        md('<div class="section-title">BUILD YOUR PROFILE</div>')
        if st.session_state.error:
            error_box(st.session_state.error)

        md('<div class="form-step">1. Add your skills</div>'
           f'<div class="form-hint">Languages, frameworks, tools or topics. Up to {skills.MAX_SKILLS}. '
           "Type anything that is not in the list.</div>")
        options = list(dict.fromkeys(skills.COMMON + list(st.session_state.skills_ms)))
        picked = st.multiselect(
            "Skills", options, key="skills_ms", accept_new_options=True,
            max_selections=skills.MAX_SKILLS, label_visibility="collapsed",
            placeholder="python, react, docker, documentation ...",
        )
        names = list(dict.fromkeys(skills.normalise_name(s) for s in picked if skills.normalise_name(s)))

        profile = []
        if names:
            md(f'<div class="form-step">2. Set your level in each</div><div class="form-hint">{LEVEL_HINT}</div>')
            for name in names:
                key = level_key(name)
                if st.session_state.get(key) not in skills.LEVELS:
                    st.session_state[key] = skills.DEFAULT_LEVEL
                name_col, level_col = st.columns([2, 3], vertical_alignment="center")
                with name_col:
                    md(f'<div class="skill-name">{esc(name)}'
                       f'<span class="kind">{skills.KINDS[skills.lookup(name).kind]}</span></div>')
                with level_col:
                    st.segmented_control(
                        f"Level in {name}", skills.LEVELS, key=key,
                        format_func=str.title, label_visibility="collapsed",
                    )
                profile.append({"skill": name, "level": st.session_state.get(key) or skills.DEFAULT_LEVEL})

        md('<div class="form-step">3. Time you have</div>')
        hours_col, button_col = st.columns([3, 2], vertical_alignment="bottom")
        with hours_col:
            hours = st.selectbox("Hours", HOURS, key="hours_sel", label_visibility="collapsed",
                                 format_func=lambda h: h if h == "a weekend" else f"{h} hours")
        with button_col:
            find = st.button("FIND ISSUES", type="primary", use_container_width=True)

        if profile:
            searches = [" + ".join(pq.skills) for pq in skills.plan_queries(profile)]
            md(f'<div class="plan">We will search: <b>{esc(" · ".join(searches))}</b></div>')

        if find:
            if not profile:
                error_box("Add at least one skill.")
                return
            st.session_state.profile = profile
            st.session_state.hours_saved = hours
            st.session_state.query = {"profile": profile, "hours": hours}
            st.session_state.error = None
            st.session_state.screen = "scan"
            st.rerun()


def render_landing():
    render_hero()
    render_profile_form()
    render_explainer()


# ---------------------------------------------------------------- screen 2


def funnel_html(rows, pending=None, total=None, finish=None):
    total = total or 1
    out = ['<div class="funnel"><h2>SCANNING</h2>']
    for label, count in rows:
        width = max(1.5, 100 * count / total) if count else 0
        out.append(
            f'<div class="frow"><div class="top"><span>{esc(label)}</span><span>{count}</span></div>'
            f'<div class="bar-bg"><div class="bar" style="width:{width:.1f}%"></div></div></div>'
        )
    if pending:
        out.append(
            f'<div class="frow pending"><div class="top"><span>{esc(pending)}</span>'
            "<span>...</span></div></div>"
        )
    if finish:
        taken, wasted = finish
        out.append(
            f'<div class="done-green">{plural(taken, "issue")} you can actually take.</div>'
            f'<div class="done-grey">{wasted} you would have wasted time on.</div>'
        )
    out.append("</div>")
    return "".join(out)


def render_scan():
    query = st.session_state.query
    profile = query["profile"]
    holder = st.empty()
    state = {"rows": [], "total": None, "pending": None}

    def draw(finish=None):
        holder.markdown(funnel_html(state["rows"], state["pending"], state["total"], finish),
                        unsafe_allow_html=True)

    def on_stage(label, count):
        if state["total"] is None:
            state["total"] = max(count, 1)
        state["rows"].append((label, count))
        state["pending"] = "scoring against your skills" if label.startswith("reading comments") else None
        draw()
        time.sleep(0.3)

    def on_progress(done, total):
        state["pending"] = f"scoring {done} of {total} against your skills"
        draw()

    try:
        search.github_token()  # clear message if missing
        judge._client()  # clear message if no local model and no GROQ_API_KEY
        state["pending"] = f"searching GitHub for {', '.join(p['skill'] for p in profile)}"
        draw()
        result = rank.run(profile, query["hours"], on_stage=on_stage, on_progress=on_progress)
    except (search.GitHubError, judge.JudgeError) as exc:
        message = str(exc)
    except requests.RequestException as exc:
        message = f"Could not reach GitHub: {exc.__class__.__name__}. Check your connection and try again."
    except Exception as exc:  # never show a traceback on screen
        message = f"Something went wrong while searching ({exc.__class__.__name__}). Try again."
    else:
        message = None
    if message:
        st.session_state.error = message
        st.session_state.screen = "landing"
        st.rerun()
        return

    state["pending"] = None
    draw(finish=(len(result["free"]), len(result["dropped"])))
    time.sleep(1.5)
    st.session_state.result = result
    st.session_state.reject_filter = None
    st.session_state.skill_filter = ALL
    st.session_state.filter_prev = ALL
    st.session_state.shown = PAGE
    st.session_state.screen = "results"
    st.rerun()


# ---------------------------------------------------------------- screen 3


def category_counts(dropped):
    counts = {c: 0 for c in CATEGORIES}
    for d in dropped:
        counts[d["category"]] = counts.get(d["category"], 0) + 1
    return counts


def render_coverage(result):
    md('<div class="label">YOUR SKILLS</div>')
    rows = []
    for row in result["coverage"]:
        if row["found"] == 0:
            status = '<div class="warn">no open beginner issues on GitHub, try a broader term</div>'
        elif row["free"] == 0:
            status = '<div class="warn">every issue found is taken or inactive</div>'
        else:
            status = ""
        rows.append(
            f'<div class="cov"><div class="head">{esc(row["skill"])} '
            f'<span class="kind">{esc(row["level"])}</span></div>'
            f'<div class="nums">checked <b>{row["found"]}</b> · free <b>{row["free"]}</b></div>{status}</div>'
        )
    md("".join(rows))


def render_summary(result):
    md('<div class="sticky-marker"></div>')
    md(
        f'<div class="summary-row"><span>CHECKED</span><b>{result["scanned"]}</b></div>'
        f'<div class="summary-row"><span>FREE</span><b>{len(result["free"])}</b></div>'
        f'<div class="summary-row"><span>REJECTED</span><b>{len(result["dropped"])}</b></div>'
    )
    render_coverage(result)
    counts = category_counts(result["dropped"])
    present = [c for c in CATEGORIES if counts.get(c)]
    if not present:
        return
    md('<div class="label">REJECTED BECAUSE</div>')
    active = st.session_state.reject_filter
    for cat in present:
        marker = ">" if active == cat else NBSP
        label = f"{marker}{NBSP}{cat.ljust(21, NBSP)}{str(counts[cat]).rjust(3, NBSP)}"
        if st.button(label, key=f"rf_{cat.replace(' ', '_')}"):
            st.session_state.reject_filter = None if active == cat else cat
            st.rerun()
    if active:
        if st.button(f"{NBSP}{NBSP}show all", key="rf_all"):
            st.session_state.reject_filter = None
            st.rerun()
    else:
        md('<div class="muted small" style="margin-top:6px">Click a reason to filter the list.</div>')


def match_chips(issue):
    chips = []
    for m in issue.get("matches", []):
        if m["strength"] == "strong":
            chips.append(f'<span class="match">{esc(m["skill"])} · {esc(m["level"])}</span>')
        else:
            chips.append(f'<span class="match weak">{esc(m["skill"])} · mentioned</span>')
    return "".join(chips)


def why_lines(issue):
    s = issue["signals"]
    if s.get("claim_count"):
        claim = f"last claim by @{s['last_claimer']} {ago(s['last_claim_days'])}, no PR since"
    else:
        claim = "claim check passed: nobody asked for it in the comments"
    evidence = ", ".join(f"{m['skill']} ({m['why']})" for m in issue.get("matches", [])) or "search match"
    needed = (issue.get("judgment") or {}).get("difficulty") or issue.get("label_difficulty")
    lines = [
        claim,
        "no open pull request linked to the issue",
        f"repo pushed {ago(s['days_since_push'])}",
        f"outside contributor PR merged {ago(s['days_since_outside_merge'])}",
        f"issue opened {ago(s['issue_age_days'])}",
        f"repo health {issue['health_score']} / 10",
        f"your skills it uses: {evidence}",
    ]
    if needed:
        lines.append(f"level it needs: {needed}; your level: {rank.working_level(issue.get('matches', []))}")
    return lines + [f"warning: {w}" for w in issue.get("warnings", [])]


def issue_header(issue, pill_class, pill_text):
    lang = issue.get("repo_language") or "language unknown"
    md(
        f'<span class="pill {pill_class}">{pill_text}</span>{match_chips(issue)}'
        f'<div class="issue-title"><a href="{esc(issue["url"])}" target="_blank">{esc(issue["title"])}</a></div>'
        f'<div class="meta">{esc(issue["repo_full_name"])} · {esc(lang)} · #{issue["number"]}</div>'
    )


def render_card(issue, rollup):
    j = issue.get("judgment")
    with st.container(border=True):
        issue_header(issue, "free", "FREE")
        md('<hr class="thin">')
        if j:
            needs = j.get("difficulty") or issue.get("label_difficulty")
            md(
                '<div class="label">WHY IT FITS YOU</div>'
                f'<div class="body-text">{esc(j["why_it_fits"])}</div>'
                '<div class="stats">'
                f'<div><b>{j["estimated_hours"]:g}h</b>hours</div>'
                f'<div><b>{j["fit"]:g}/10</b>fit</div>'
                f'<div><b>{j["clarity"]:g}/10</b>clarity</div>'
                + (f"<div><b>{esc(needs)}</b>level needed</div>" if needs else "")
                + "</div>"
                '<div class="label">FIRST HOUR</div>'
                '<ol class="steps-list">' + "".join(f"<li>{esc(step)}</li>" for step in j["first_steps"]) + "</ol>"
            )
        else:
            md(
                '<div class="body-text">Not scored yet. This issue passed every availability check, '
                "but only the strongest candidates are scored so the search stays fast. "
                "Open it and judge the fit yourself.</div>"
            )

        risks = list((j or {}).get("risks", [])) + list(issue.get("warnings", []))
        if risks:
            with st.expander(f"Red flags ({len(risks)})"):
                md('<ul class="steps-list">' + "".join(f"<li>{esc(r)}</li>" for r in risks) + "</ul>")

        with st.expander("why?"):
            md('<ul class="steps-list">' + "".join(f"<li>{esc(line)}</li>" for line in why_lines(issue)) + "</ul>")

        others = rollup.get(issue["repo_full_name"], 1) - 1
        if others > 0:
            md(f'<div class="rollup">{plural(others, "more free issue")} in this repo</div>')

        if j:
            md('<div class="label">CLAIM IT</div>')
            try:
                st.code(j["claim_comment"], language=None, wrap_lines=True)
            except TypeError:  # older Streamlit without wrap_lines
                st.code(j["claim_comment"], language=None)
            md('<div class="muted small">We never post. You do.</div>')


def render_stale(issue):
    s = issue["signals"]
    with st.container(border=True):
        issue_header(issue, "stale", "STALE CLAIM")
        md(
            f'<div class="body-text" style="margin-top:10px">@{esc(s.get("last_claimer", "someone"))} '
            f'claimed this {s.get("last_claim_days", "?")} days ago and never opened a PR.</div>'
        )


def render_wall(result):
    dropped = result["dropped"]
    active = st.session_state.reject_filter
    shown = [d for d in dropped if active is None or d["category"] == active]
    if dropped:
        rows = "".join(
            f'<div class="wall-row"><a class="reject" href="{esc(d["url"])}" target="_blank" '
            f'title="{esc(d["repo_full_name"])}">{esc(d["title"])}</a>'
            f'<span class="why">{esc(d["reason"])}</span></div>'
            for d in shown
        )
        note = f'<div class="muted small" style="margin-bottom:6px">showing: {esc(active)}</div>' if active else ""
        tail = '<div class="muted small" style="margin-top:12px">Click any title and check it yourself.</div>'
    else:
        rows = note = ""
        tail = '<div class="muted small">Every issue we found passed the checks.</div>'
    md(
        '<div class="wall"><h3>WHAT OTHER TOOLS WOULD SHOW YOU</h3>'
        f'<div class="sub">{len(dropped)} of these look open on GitHub right now.</div>'
        f"{note}{rows}{tail}</div>"
    )


def _uses(issue, skill):
    return any(m["skill"] == skill for m in issue.get("matches", []))


def render_issue_list(result):
    free = result["free"]
    profile = result["profile"]
    counts = {p["skill"]: sum(1 for i in free if _uses(i, p["skill"])) for p in profile}

    # Only skills with something to show are filter options; the note below
    # and the coverage panel explain the rest.
    options = [ALL, *(k for k, n in counts.items() if n)]
    if st.session_state.get("skill_filter") not in options:
        st.session_state.skill_filter = ALL
    labels = {ALL: f"All {len(free)}", **{k: f"{k} {n}" for k, n in counts.items()}}
    choice = ALL
    if len(options) > 2:  # a filter is only useful with two or more skills to choose between
        choice = st.segmented_control(
            "Show issues for", options, key="skill_filter",
            format_func=labels.get, label_visibility="collapsed",
        ) or ALL
    if choice != st.session_state.filter_prev:
        st.session_state.filter_prev = choice
        st.session_state.shown = PAGE

    empty = [k for k, n in counts.items() if n == 0]
    if empty and free:
        md(f'<div class="note">Nothing free right now for <b>{esc(", ".join(empty))}</b>. '
           "The issues below match your other skills.</div>")

    items = free if choice == ALL else [i for i in free if _uses(i, choice)]
    if not items:
        md(
            '<div class="label">NO FREE ISSUES LEFT</div>'
            f'<div class="body-text">All {result["scanned"]} issues we checked are taken, stale or in '
            "inactive repos. Try different skills with EDIT SEARCH.</div>"
        )
    for issue in items[:st.session_state.shown]:
        render_card(issue, result["rollup"])
    left = len(items) - st.session_state.shown
    if left > 0:
        if st.button(f"SHOW {min(PAGE, left)} MORE  ({left} left)", key="more", use_container_width=True):
            st.session_state.shown += PAGE
            st.rerun()

    if result["stale"]:
        md('<div class="label" style="margin-top:28px">WORTH ASKING ABOUT</div>')
        for issue in result["stale"]:
            render_stale(issue)


def render_empty(result):
    skills_text = ", ".join(result["skills"])
    md(
        '<div class="page hero"><div class="eyebrow">NOTHING FOUND</div>'
        f'<div class="sub">GitHub has no open, unassigned beginner issues for <b>{esc(skills_text)}</b> '
        "right now. Try broader skills, for example a language like python or javascript, or a topic "
        "like documentation or testing.</div></div>"
    )
    with st.container(key="empty_actions"):
        if st.button("TRY DIFFERENT SKILLS", type="primary"):
            st.session_state.screen = "landing"
            st.rerun()


def render_results():
    result = st.session_state.result
    if result["scanned"] == 0:
        render_empty(result)
        return
    profile_col, button_col = st.columns([5, 1], vertical_alignment="center")
    with profile_col:
        chips = "".join(f'<span class="chip">{esc(p["skill"])} <span class="muted">{esc(p["level"])}</span></span>'
                        for p in result["profile"])
        md(f'<span class="muted small" style="margin-right:8px">YOUR PROFILE</span>{chips}')
    with button_col:
        if st.button("EDIT SEARCH", use_container_width=True):
            st.session_state.screen = "landing"
            st.rerun()

    left, middle, right = st.columns([1, 2, 1.6], gap="large")
    with left:
        render_summary(result)
    with middle:
        render_issue_list(result)
    with right:
        render_wall(result)


# ---------------------------------------------------------------- router

screen = st.session_state.screen
if screen == "results" and st.session_state.result:
    render_results()
elif screen == "scan" and st.session_state.query:
    render_scan()
else:
    render_landing()
footer()
