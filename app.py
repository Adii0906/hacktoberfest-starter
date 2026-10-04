"""HACKTOBERFEST STARTER. GitHub says unassigned. We check if it is actually unclaimed."""

import html
import json
import os
import time

import requests
import streamlit as st

from core import judge, rank, search

st.set_page_config(
    page_title="HACKTOBERFEST STARTER",
    layout="wide",
    initial_sidebar_state="collapsed",
)

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
.pill.free { color: #3FB950; border: 1px solid #3FB950; background: rgba(63,185,80,.08); }
.pill.stale { color: #D29922; border: 1px solid #D29922; background: rgba(210,153,34,.08); }
.reject { color: #F85149; text-decoration: line-through; opacity: .75; }
a.reject:hover { opacity: 1; }
.muted { color: #8B949E; }
.small { font-size: 12px; }
.label { color: #8B949E; font-size: 11px; letter-spacing: 1px; text-transform: uppercase; margin: 14px 0 4px; }
.model { color: #6E7681; font-size: 10px; letter-spacing: 0; text-transform: none; margin-left: 6px; }
.hero { text-align: center; margin: 2.5rem 0 2rem; }
.hero h1 { font-size: 40px; letter-spacing: 6px; color: #C9D1D9; margin: 0; }
.hero p { color: #8B949E; font-size: 16px; margin-top: 8px; }
.step-num { color: #3FB950; font-size: 12px; letter-spacing: 1px; }
.step-title { font-size: 18px; font-weight: 700; margin: 4px 0 8px; }
.step-body { color: #8B949E; font-size: 13px; line-height: 1.5; }
.tagline { text-align: center; color: #6E7681; margin: 1.5rem 0 2rem; font-size: 13px; }
.chip {
  display: inline-block; padding: 2px 10px; margin: 0 6px 6px 0; border-radius: 999px;
  border: 1px solid #30363D; background: #161B22; font-size: 12px; color: #C9D1D9;
}
.err {
  border: 1px solid #F85149; border-radius: 6px; padding: 10px 14px; color: #F85149;
  background: rgba(248,81,73,.06); font-size: 13px; margin: 8px 0;
}
.funnel { max-width: 720px; margin: 4rem auto 0; }
.funnel h2 { letter-spacing: 6px; font-size: 20px; margin-bottom: 1.5rem; }
.frow { margin: 0 0 14px; }
.frow .top { display: flex; justify-content: space-between; font-size: 14px; }
.frow .bar-bg { background: #161B22; height: 8px; border-radius: 4px; margin-top: 6px; }
.frow .bar { background: #3FB950; height: 8px; border-radius: 4px; transition: width .4s; }
.frow.pending .top { color: #6E7681; }
.done-green { color: #3FB950; font-size: 18px; font-weight: 700; margin-top: 1.5rem; }
.done-grey { color: #8B949E; font-size: 16px; }
.issue-title a { font-size: 16px; font-weight: 700; color: #C9D1D9; text-decoration: none; }
.issue-title a:hover { color: #3FB950; }
.thin { border: 0; border-top: 1px solid #21262D; margin: 10px 0; }
.stats { display: flex; gap: 24px; margin: 10px 0; }
.stats div { font-size: 12px; color: #8B949E; }
.stats b { color: #C9D1D9; font-size: 15px; display: block; }
ol.steps { padding-left: 20px; margin: 0; font-size: 13px; }
.rollup { color: #3FB950; font-size: 12px; margin: 8px 0; }
.summary-row { display: flex; justify-content: space-between; font-size: 13px; padding: 2px 0; }
.summary-row b { color: #C9D1D9; }
.wall { border-left: 3px solid #F85149; padding: 4px 0 4px 18px; }
.wall h3 { color: #F85149; font-size: 15px; letter-spacing: 2px; margin: 0; }
.wall .sub { color: #8B949E; font-size: 13px; margin: 4px 0 14px; }
.wall-row { display: flex; justify-content: space-between; gap: 12px; font-size: 13px;
  padding: 5px 0; border-bottom: 1px solid #161B22; }
.wall-row a { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.wall-row .why { color: #F85149; white-space: nowrap; font-size: 12px; }
div[data-testid="stColumn"]:has(.sticky-marker), div[data-testid="column"]:has(.sticky-marker) {
  position: sticky; top: 2rem; align-self: flex-start;
}
[class*="st-key-rf_"] button {
  background: transparent; border: none; padding: 2px 0; min-height: 0;
  justify-content: flex-start; color: #8B949E;
}
[class*="st-key-rf_"] button:hover { color: #F85149; background: transparent; }
.app-footer {
  position: fixed; left: 0; right: 0; bottom: 0; padding: 8px 16px; text-align: center;
  font-size: 12px; color: #6E7681; background: #0D1117; border-top: 1px solid #21262D; z-index: 100;
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
DEMO_FILE = os.path.join(os.path.dirname(__file__), "demo", "cached_run.json")
MODEL_NAME = judge.MODEL.split("/")[-1]
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


def footer():
    md(
        f'<div class="app-footer">Deterministic filters decide what is available. '
        f"{MODEL_NAME} decides what fits you. Both are shown, neither is hidden.</div>"
    )


# ---------------------------------------------------------------- top bar

has_token = bool(os.environ.get("GITHUB_TOKEN", "").strip())
_, toggle_col = st.columns([6, 1])
with toggle_col:
    demo_mode = st.toggle("Demo mode", value=not has_token, key="demo_mode")


# ---------------------------------------------------------------- screen 1


def render_landing():
    md(
        '<div class="hero"><h1>HACKTOBERFEST STARTER</h1>'
        "<p>Open source issues that are actually free.</p></div>"
    )
    steps = [
        ("01", "SEARCH", "GitHub gives us every unassigned beginner issue for your skills."),
        ("02", "VET", "We check what GitHub cannot: who already claimed it in the comments, open PRs, dead repos."),
        ("03", "MATCH", f"{MODEL_NAME} reads what is left and ranks it against your skills."),
    ]
    for col, (num, title, body) in zip(st.columns(3, border=True), steps):
        with col:
            md(
                f'<div class="step-num">{num}</div><div class="step-title">{title}</div>'
                f'<div class="step-body">{body}</div>'
            )
    md('<div class="tagline">GitHub says unassigned. We check if it is actually unclaimed.</div>')

    if st.session_state.error:
        error_box(st.session_state.error)

    skills_col, hours_col, button_col = st.columns([5, 1.3, 1], vertical_alignment="bottom")
    with skills_col:
        picked = st.multiselect(
            "YOUR SKILLS",
            COMMON_SKILLS,
            default=["python", "sql"],
            accept_new_options=True,
            placeholder="type any skill",
        )
    with hours_col:
        hours = st.selectbox("HOURS", HOURS, index=1)
    with button_col:
        find = st.button("FIND", type="primary", use_container_width=True)

    skills = list(dict.fromkeys(s.strip().lower() for s in picked if s.strip()))
    if skills:
        chips = "".join(
            f'<span class="chip">{esc(s)} '
            f'<span class="muted">{"language" if s in search.LANGUAGES else "keyword"}</span></span>'
            for s in skills
        )
        md(f'<div style="margin-top:8px">{chips}</div>')
    if demo_mode:
        md('<div class="muted small">Demo mode: replays a saved real run, zero network calls.</div>')

    if find:
        if not skills:
            error_box("Pick at least one skill.")
            return
        st.session_state.query = {"skills": skills, "hours": hours, "demo": demo_mode}
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
        out.append(f'<div class="frow pending"><div class="top"><span>{esc(pending)}</span><span>...</span></div></div>')
    if finish:
        taken, wasted = finish
        out.append(
            f'<div class="done-green">{taken} issues you can actually take.</div>'
            f'<div class="done-grey">{wasted} you would have wasted time on.</div>'
        )
    out.append("</div>")
    return "".join(out)


def load_demo():
    if not os.path.exists(DEMO_FILE):
        raise FileNotFoundError(
            "demo/cached_run.json not found. Generate it with a real run: "
            "python -m core.rank --skills python,sql --hours 4 --save-demo"
        )
    with open(DEMO_FILE) as f:
        return json.load(f)


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
        if query["demo"]:
            result = load_demo()
            for step in result["funnel"]:
                on_stage(step["label"], step["count"])
        else:
            search.github_token()  # clear message if missing
            judge._client()  # clear message if GROQ_API_KEY missing
            holder.markdown(
                funnel_html([], pending=f"fetching issues for {', '.join(query['skills'])}"),
                unsafe_allow_html=True,
            )
            with st.spinner(f"{MODEL_NAME} is reading the survivors"):
                result = rank.run(query["skills"], query["hours"], on_stage=on_stage)
    except (search.GitHubError, judge.JudgeError, FileNotFoundError) as exc:
        st.session_state.error = str(exc)
        st.session_state.screen = "landing"
        st.rerun()
        return
    except requests.RequestException as exc:
        st.session_state.error = f"Network error talking to GitHub: {exc}"

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
    counts = category_counts(result["dropped"])
    md(
        f'<div class="summary-row"><span class="muted">SKILLS</span><b>{esc(", ".join(result["skills"]))}</b></div>'
        f'<div class="summary-row"><span class="muted">SCANNED</span><b>{result["scanned"]}</b></div>'
        f'<div class="summary-row"><span class="muted">TAKEN</span><b>{len(result["top"])}</b></div>'
        '<hr class="thin">'
    )
    active = st.session_state.reject_filter
    for cat in CATEGORIES:
        n = counts.get(cat, 0)
        marker = ">" if active == cat else NBSP
        label = f"{marker}{NBSP}{cat.ljust(21, NBSP)}{str(n).rjust(3, NBSP)}"
        if st.button(label, key=f"rf_{cat.replace(' ', '_')}", disabled=n == 0):
            st.session_state.reject_filter = None if active == cat else cat
            st.rerun()
    md('<div class="muted small" style="margin-top:6px">click a line to filter the wall</div>')


def why_lines(issue):
    s = issue["signals"]
    if s.get("claim_count"):
        claim = f"last claim by @{s['last_claimer']} {ago(s['last_claim_days'])}, no PR since"
    else:
        claim = "claim check passed: nobody asked for it in the comments"
    lines = [
        claim,
        "no open pull request linked on the timeline",
        f"repo pushed {ago(s['days_since_push'])}",
        f"outside PR merged {ago(s['days_since_outside_merge'])}",
        f"issue opened {ago(s['issue_age_days'])}",
        f"repo health {issue['health_score']} / 10",
    ]
    return lines + [f"warning: {w}" for w in issue.get("warnings", [])]


def render_card(issue, rollup):
    j = issue.get("judgment")
    with st.container(border=True):
        lang = issue.get("repo_language") or "unknown"
        md(
            '<span class="pill free">FREE</span>'
            f'<div class="issue-title" style="margin-top:8px"><a href="{esc(issue["url"])}" target="_blank">'
            f'{esc(issue["title"])}</a></div>'
            f'<div class="muted small">{esc(issue["repo_full_name"])} · {esc(lang)} · #{issue["number"]}</div>'
            '<hr class="thin">'
        )
        if j:
            md(
                f'<div class="label">WHY IT FITS YOU<span class="model">{MODEL_NAME}</span></div>'
                f'<div style="font-size:14px">{esc(j["why_it_fits"])}</div>'
                '<div class="stats">'
                f'<div><b>{j["estimated_hours"]:g}h</b>hours</div>'
                f'<div><b>{j["fit"]:g}/10</b>fit</div>'
                f'<div><b>{j["clarity"]:g}/10</b>clarity</div>'
                "</div>"
                f'<div class="label">FIRST HOUR<span class="model">{MODEL_NAME}</span></div>'
                '<ol class="steps">' + "".join(f"<li>{esc(step)}</li>" for step in j["first_steps"]) + "</ol>"
            )
        else:
            md(f'<div class="muted small">Not judged: {MODEL_NAME} was unavailable for this issue. '
               "The vet checks below still passed.</div>")

        with st.expander("Red flags"):
            risks = (j or {}).get("risks", [])
            if risks:
                md(f'<div class="label">FROM {MODEL_NAME}</div>')
                for r in risks:
                    md(f"- {esc(r)}")
            for w in issue.get("warnings", []):
                md(f"- {esc(w)} (deterministic check)")
            if not risks and not issue.get("warnings"):
                md('<span class="muted small">none found</span>')

        with st.expander("why?"):
            for line in why_lines(issue):
                md(f'<div class="small">{esc(line)}</div>')

        others = rollup.get(issue["repo_full_name"], 1) - 1
        if others > 0:
            md(f'<div class="rollup">{others} more free issue{"s" if others != 1 else ""} in this repo</div>')

        if j:
            md(f'<div class="label">CLAIM IT<span class="model">draft by {MODEL_NAME}</span></div>')
            try:
                st.code(j["claim_comment"], language=None, wrap_lines=True)
            except TypeError:  # older Streamlit without wrap_lines
                st.code(j["claim_comment"], language=None)
            md('<div class="muted small">We never post. You do.</div>')


def render_stale(issue):
    s = issue["signals"]
    with st.container(border=True):
        md(
            '<span class="pill stale">STALE CLAIM</span>'
            f'<div class="issue-title" style="margin-top:8px"><a href="{esc(issue["url"])}" target="_blank">'
            f'{esc(issue["title"])}</a></div>'
            f'<div class="muted small">{esc(issue["repo_full_name"])} · {esc(issue.get("repo_language") or "unknown")}</div>'
            f'<div style="margin-top:8px;font-size:14px">@{esc(s.get("last_claimer", "someone"))} claimed this '
            f'{s.get("last_claim_days", "?")} days ago and never opened a PR.</div>'
        )


def render_wall(result):
    dropped = result["dropped"]
    active = st.session_state.reject_filter
    shown = [d for d in dropped if active is None or d["category"] == active]
    rows = "".join(
        f'<div class="wall-row"><a class="reject" href="{esc(d["url"])}" target="_blank" '
        f'title="{esc(d["repo_full_name"])}">{esc(d["title"])}</a>'
        f'<span class="why">{esc(d["reason"])}</span></div>'
        for d in shown
    )
    filter_note = f'<div class="muted small" style="margin-bottom:8px">showing: {esc(active)}</div>' if active else ""
    md(
        '<div class="wall"><h3>WHAT OTHER TOOLS WOULD SHOW YOU</h3>'
        f'<div class="sub">{len(dropped)} of these look open on GitHub right now.</div>'
        f"{filter_note}{rows}"
        '<div class="muted small" style="margin-top:10px">Click any title and check it yourself.</div>'
        "</div>"
    )


def render_results():
    result = st.session_state.result
    if st.button("NEW SEARCH"):
        st.session_state.screen = "landing"
        st.rerun()

    left, middle, right = st.columns([1, 2, 1.6], gap="large")
    with left:
        render_summary(result)
    with middle:
        if not result["top"]:
            md('<div class="muted">Nothing survived vetting for these skills. Try adding another skill.</div>')
        for issue in result["top"]:
            render_card(issue, result["rollup"])
        if result["stale"]:
            md('<div class="label" style="margin-top:28px;font-size:13px">WORTH ASKING ABOUT</div>')
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
