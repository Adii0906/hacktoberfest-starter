"""HACKTOBERFEST STARTER. GitHub says unassigned. We check if it is actually unclaimed."""

import html
import os
import time

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # reads GITHUB_TOKEN and GROQ_API_KEY from .env

from core import judge, rank, search  # noqa: E402

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
  display: inline-block; padding: 2px 10px; border-radius: 999px;
  font-size: 11px; letter-spacing: 1px; text-transform: uppercase; font-weight: 700;
}
.pill.free { color: #3FB950; border: 1px solid #3FB950; }
.pill.stale { color: #E3B341; border: 1px solid #E3B341; }
.muted { color: #9DA7B3; }
.small { font-size: 13px; }
.label { color: #9DA7B3; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; margin: 16px 0 6px; }
.rule { border: 0; border-top: 1px solid #30363D; margin: 28px 0; }

.hero { max-width: 760px; margin: 3rem auto 0; }
.hero h1 { font-size: 40px; letter-spacing: 6px; color: #E6EDF3; margin: 0; line-height: 1.2; }
.hero .sub { color: #C9D1D9; font-size: 18px; margin-top: 12px; line-height: 1.5; }
.steps { max-width: 760px; margin: 0 auto; }
.step { display: flex; gap: 28px; padding: 18px 0; align-items: baseline; }
.step + .step { border-top: 1px solid #21262D; }
.step .name { flex: 0 0 110px; font-size: 14px; font-weight: 700; letter-spacing: 2px; color: #9DA7B3; }
.step .text { font-size: 15px; line-height: 1.6; color: #C9D1D9; }
.step.key .name { color: #3FB950; font-size: 20px; }
.step.key .text { color: #E6EDF3; font-size: 18px; font-weight: 600; }
.tagline { max-width: 760px; margin: 0 auto; color: #9DA7B3; font-size: 14px; }
.form-head { max-width: 760px; margin: 0 auto 8px; }

.chip {
  display: inline-block; padding: 3px 10px; margin: 0 6px 6px 0; border-radius: 999px;
  border: 1px solid #30363D; background: #161B22; font-size: 13px; color: #E6EDF3;
}
.chip .muted { font-size: 11px; }
.err {
  border-left: 3px solid #FF7B72; padding: 8px 14px; color: #FF7B72;
  font-size: 14px; margin: 12px 0; line-height: 1.5;
}

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
ol.steps-list { padding-left: 22px; margin: 0; font-size: 14px; line-height: 1.6; color: #C9D1D9; }
.rollup { color: #3FB950; font-size: 13px; margin: 10px 0; }

.summary-row { display: flex; justify-content: space-between; gap: 12px; font-size: 14px; padding: 3px 0; color: #9DA7B3; }
.summary-row b { color: #E6EDF3; text-align: right; overflow-wrap: anywhere; }

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

COMMON_SKILLS = [
    "python", "javascript", "typescript", "react", "go", "rust", "java", "c++",
    "sql", "html", "css", "docker", "machine learning", "devops",
]
HOURS = ["2", "4", "8", "a weekend"]
CATEGORIES = [
    "already claimed", "open PR exists", "dead repo", "stale issue",
    "maintainers inactive", "bans AI PRs", "too vague",
]
NBSP = " "

for key, default in {
    "screen": "landing",
    "result": None,
    "query": None,
    "error": None,
    "reject_filter": None,
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


def footer():
    md(
        '<div class="app-footer">Fixed rules decide what is available. '
        "Ranking decides what fits you. Both are shown, nothing is hidden.</div>"
    )


# ---------------------------------------------------------------- screen 1


def render_landing():
    md(
        '<div class="hero"><h1>HACKTOBERFEST STARTER</h1>'
        '<div class="sub">Find beginner open source issues that nobody has taken yet, '
        "matched to the skills you already have.</div></div>"
        '<hr class="rule">'
        '<div class="steps">'
        '<div class="step"><div class="name">SEARCH</div>'
        '<div class="text">We pull unassigned beginner issues for your skills.</div></div>'
        '<div class="step key"><div class="name">VERIFY</div>'
        '<div class="text">We check what GitHub cannot: who already claimed it in the comments, '
        "open PRs, dead repos, maintainers who ban AI PRs.</div></div>"
        '<div class="step"><div class="name">MATCH</div>'
        '<div class="text">We rank what survives against your skills.</div></div>'
        "</div>"
        '<hr class="rule">'
        '<div class="tagline">GitHub says unassigned. We check if it is actually unclaimed.</div>'
        '<hr class="rule">'
    )

    _, form, _ = st.columns([1, 4, 1])
    with form:
        if st.session_state.error:
            error_box(st.session_state.error)

        skills_col, hours_col, button_col = st.columns([4, 1.4, 1], vertical_alignment="bottom")
        with skills_col:
            picked = st.multiselect(
                "YOUR SKILLS",
                COMMON_SKILLS,
                default=["python", "sql"],
                accept_new_options=True,
                placeholder="pick or type any skill",
            )
        with hours_col:
            hours = st.selectbox("HOURS YOU HAVE", HOURS, index=1)
        with button_col:
            find = st.button("FIND", type="primary", use_container_width=True)

        skills = list(dict.fromkeys(s.strip().lower() for s in picked if s.strip()))
        if skills:
            chips = "".join(
                f'<span class="chip">{esc(s)} '
                f'<span class="muted">{"language" if s in search.LANGUAGES else "keyword"}</span></span>'
                for s in skills
            )
            md(f'<div style="margin-top:10px"><span class="muted small">searching for </span>{chips}</div>')

        if find:
            if not skills:
                error_box("Pick at least one skill.")
                return
            st.session_state.query = {"skills": skills, "hours": hours}
            st.session_state.error = None
            st.session_state.screen = "scan"
            st.rerun()


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
    holder = st.empty()
    rows = []
    state = {"total": None}

    def on_stage(label, count):
        if state["total"] is None:
            state["total"] = max(count, 1)
        rows.append((label, count))
        holder.markdown(funnel_html(rows, total=state["total"]), unsafe_allow_html=True)
        time.sleep(0.4)

    try:
        search.github_token()  # clear message if missing
        judge._client()  # clear message if GROQ_API_KEY missing
        holder.markdown(
            funnel_html([], pending=f"fetching issues for {', '.join(query['skills'])}"),
            unsafe_allow_html=True,
        )
        with st.spinner("ranking what survived"):
            result = rank.run(query["skills"], query["hours"], on_stage=on_stage)
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

    holder.markdown(
        funnel_html(
            rows,
            total=state["total"],
            finish=(len(result["top"]), len(result["dropped"])),
        ),
        unsafe_allow_html=True,
    )
    time.sleep(1.5)
    st.session_state.result = result
    st.session_state.reject_filter = None
    st.session_state.screen = "results"
    st.rerun()


# ---------------------------------------------------------------- screen 3


def category_counts(dropped):
    counts = {c: 0 for c in CATEGORIES}
    for d in dropped:
        counts[d["category"]] = counts.get(d["category"], 0) + 1
    return counts


def render_summary(result):
    md('<div class="sticky-marker"></div>')
    md(
        f'<div class="summary-row"><span>SKILLS</span><b>{esc(", ".join(result["skills"]))}</b></div>'
        f'<div class="summary-row"><span>SCANNED</span><b>{result["scanned"]}</b></div>'
        f'<div class="summary-row"><span>TAKEN</span><b>{len(result["top"])}</b></div>'
        '<hr class="thin">'
    )
    counts = category_counts(result["dropped"])
    present = [c for c in CATEGORIES if counts.get(c)]
    if not present:
        md('<div class="muted small">Nothing was rejected.</div>')
        return
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


def why_lines(issue):
    s = issue["signals"]
    if s.get("claim_count"):
        claim = f"last claim by @{s['last_claimer']} {ago(s['last_claim_days'])}, no PR since"
    else:
        claim = "claim check passed: nobody asked for it in the comments"
    lines = [
        claim,
        "no open pull request linked to the issue",
        f"repo pushed {ago(s['days_since_push'])}",
        f"outside contributor PR merged {ago(s['days_since_outside_merge'])}",
        f"issue opened {ago(s['issue_age_days'])}",
        f"repo health {issue['health_score']} / 10",
    ]
    return lines + [f"warning: {w}" for w in issue.get("warnings", [])]


def issue_header(issue, pill_class, pill_text):
    lang = issue.get("repo_language") or "language unknown"
    md(
        f'<span class="pill {pill_class}">{pill_text}</span>'
        f'<div class="issue-title"><a href="{esc(issue["url"])}" target="_blank">{esc(issue["title"])}</a></div>'
        f'<div class="meta">{esc(issue["repo_full_name"])} · {esc(lang)} · #{issue["number"]}</div>'
    )


def render_card(issue, rollup):
    j = issue.get("judgment")
    with st.container(border=True):
        issue_header(issue, "free", "FREE")
        md('<hr class="thin">')
        if j:
            md(
                '<div class="label">WHY IT FITS YOU</div>'
                f'<div class="body-text">{esc(j["why_it_fits"])}</div>'
                '<div class="stats">'
                f'<div><b>{j["estimated_hours"]:g}h</b>hours</div>'
                f'<div><b>{j["fit"]:g}/10</b>fit</div>'
                f'<div><b>{j["clarity"]:g}/10</b>clarity</div>'
                "</div>"
                '<div class="label">FIRST HOUR</div>'
                '<ol class="steps-list">' + "".join(f"<li>{esc(step)}</li>" for step in j["first_steps"]) + "</ol>"
            )
        else:
            md(
                '<div class="body-text">Ranking was not available for this issue, '
                "so it has no fit score. Every availability check below still passed.</div>"
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


def render_empty(result):
    skills = ", ".join(result["skills"])
    md(
        '<div class="hero"><h1 style="font-size:28px">NOTHING FOUND</h1>'
        f'<div class="sub">GitHub has no open, unassigned beginner issues for <b>{esc(skills)}</b> '
        "right now. Try different or broader skills, for example a language like python or javascript.</div></div>"
    )
    _, mid, _ = st.columns([1, 4, 1])
    with mid:
        if st.button("TRY DIFFERENT SKILLS", type="primary"):
            st.session_state.screen = "landing"
            st.rerun()


def render_results():
    result = st.session_state.result
    if result["scanned"] == 0:
        render_empty(result)
        return
    if st.button("NEW SEARCH"):
        st.session_state.screen = "landing"
        st.rerun()

    left, middle, right = st.columns([1, 2, 1.6], gap="large")
    with left:
        render_summary(result)
    with middle:
        if not result["top"]:
            md(
                '<div class="label">NO FREE ISSUES LEFT</div>'
                f'<div class="body-text">All {result["scanned"]} issues we found are taken, stale or in '
                "inactive repos. Try different skills with NEW SEARCH.</div>"
            )
        for issue in result["top"]:
            render_card(issue, result["rollup"])
        if result["stale"]:
            md('<div class="label" style="margin-top:28px">WORTH ASKING ABOUT</div>')
            for issue in result["stale"]:
                render_stale(issue)
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
