"""Skill catalog, profile normalisation, issue-to-skill matching and the
search plan.

Why this module exists
----------------------
A skill is not always a GitHub language. "react" lives in JavaScript and
TypeScript repos, "sql" mostly lives inside Python, Java or Go repos rather
than repos whose primary language is SQL, and "docs" is not a language at
all. Searching every skill as ``language:<skill>`` returns almost nothing
for those skills, so results collapse onto whichever language skill has the
most issues. Every skill therefore gets a search strategy that suits its
kind, and pairs of skills get combined queries so issues needing both are
found directly.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

LEVELS = ("beginner", "intermediate", "advanced")
DEFAULT_LEVEL = "intermediate"
MAX_SKILLS = 8

KINDS = {
    "language": "language",
    "framework": "framework",
    "tool": "tool",
    "topic": "topic",
    "custom": "keyword",
}


@dataclass(frozen=True)
class SkillSpec:
    key: str                 # canonical lower-case name
    kind: str                # language | framework | tool | topic | custom
    languages: tuple = ()    # GitHub linguist names the skill usually lives in
    term: str = ""           # search term for non-language skills
    aliases: tuple = ()      # extra words that count as a mention


def _language(key, *languages, aliases=()):
    return SkillSpec(key, "language", languages, "", aliases)


def _keyword(kind, key, term=None, languages=(), aliases=()):
    return SkillSpec(key, kind, tuple(languages), term or key, tuple(aliases))


CATALOG = {spec.key: spec for spec in [
    _language("python", "Python"),
    _language("javascript", "JavaScript"),
    _language("typescript", "TypeScript"),
    _language("go", "Go"),
    _language("rust", "Rust"),
    _language("java", "Java"),
    _language("c", "C"),
    _language("c++", "C++"),
    _language("c#", "C#"),
    _language("ruby", "Ruby"),
    _language("php", "PHP"),
    _language("kotlin", "Kotlin"),
    _language("swift", "Swift"),
    _language("dart", "Dart"),
    _language("scala", "Scala"),
    _language("elixir", "Elixir"),
    _language("haskell", "Haskell"),
    _language("lua", "Lua"),
    _language("r", "R"),
    _language("julia", "Julia"),
    _language("shell", "Shell"),
    _language("html", "HTML"),
    _language("css", "CSS", "SCSS"),
    _keyword("topic", "sql", languages=("SQL", "PLpgSQL", "TSQL"),
             aliases=("postgres", "postgresql", "mysql", "sqlite", "database", "query")),
    _keyword("framework", "react", languages=("JavaScript", "TypeScript"), aliases=("jsx", "tsx")),
    _keyword("framework", "vue", languages=("Vue", "JavaScript", "TypeScript"), aliases=("vuejs", "nuxt")),
    _keyword("framework", "angular", languages=("TypeScript",)),
    _keyword("framework", "svelte", languages=("Svelte", "JavaScript", "TypeScript"), aliases=("sveltekit",)),
    _keyword("framework", "next.js", term="nextjs", languages=("JavaScript", "TypeScript"), aliases=("next.js",)),
    _keyword("framework", "node", languages=("JavaScript", "TypeScript"), aliases=("nodejs", "node.js", "express")),
    _keyword("framework", "django", languages=("Python",)),
    _keyword("framework", "flask", languages=("Python",)),
    _keyword("framework", "fastapi", languages=("Python",)),
    _keyword("framework", "pandas", languages=("Python", "Jupyter Notebook"), aliases=("dataframe",)),
    _keyword("framework", "pytorch", languages=("Python", "Jupyter Notebook"), aliases=("torch",)),
    _keyword("framework", "tensorflow", languages=("Python", "Jupyter Notebook"), aliases=("keras",)),
    _keyword("framework", "spring", languages=("Java", "Kotlin"), aliases=("spring boot",)),
    _keyword("framework", "rails", languages=("Ruby",), aliases=("ruby on rails",)),
    _keyword("framework", "laravel", languages=("PHP",)),
    _keyword("framework", "flutter", languages=("Dart",)),
    _keyword("framework", "android", languages=("Kotlin", "Java")),
    _keyword("framework", "tailwind", languages=("HTML", "CSS", "JavaScript", "TypeScript"), aliases=("tailwindcss",)),
    _keyword("tool", "docker", aliases=("dockerfile", "container", "docker-compose")),
    _keyword("tool", "kubernetes", aliases=("k8s", "helm")),
    _keyword("tool", "terraform", languages=("HCL",)),
    _keyword("tool", "github actions", aliases=("workflow", "ci")),
    _keyword("tool", "git"),
    _keyword("topic", "machine learning", languages=("Python", "Jupyter Notebook"),
             aliases=("ml", "model training", "neural network")),
    _keyword("topic", "data science", languages=("Python", "Jupyter Notebook", "R"), aliases=("data analysis",)),
    _keyword("topic", "devops", aliases=("ci", "deployment", "pipeline")),
    _keyword("topic", "testing", term="tests", aliases=("test", "unit test", "pytest", "jest")),
    _keyword("topic", "documentation", aliases=("docs", "readme", "typo")),
    _keyword("topic", "accessibility", aliases=("a11y", "aria", "screen reader")),
    _keyword("topic", "ui design", term="ui", aliases=("ux", "design", "layout")),
    _keyword("topic", "security", aliases=("vulnerability", "auth")),
]}

ALIASES = {
    "js": "javascript", "ts": "typescript", "golang": "go", "cpp": "c++",
    "csharp": "c#", "py": "python", "k8s": "kubernetes", "ml": "machine learning",
    "nextjs": "next.js", "node.js": "node", "nodejs": "node", "docs": "documentation",
    "postgres": "sql", "postgresql": "sql", "mysql": "sql", "bash": "shell",
    "vuejs": "vue", "reactjs": "react", "react.js": "react", "tests": "testing",
    "ci": "github actions", "ux": "ui design", "ui": "ui design", "a11y": "accessibility",
}

# Suggested in the skills picker, in this order.
COMMON = [
    "python", "javascript", "typescript", "react", "node", "go", "rust", "java",
    "c++", "sql", "html", "css", "docker", "django", "machine learning",
    "devops", "documentation", "testing",
]

# Beginner-friendly labels, tried in this order, by the contributor's level.
LABELS_BY_LEVEL = {
    "beginner": ("good first issue", "good-first-issue", "first-timers-only", "beginner", "easy"),
    "intermediate": ("good first issue", "help wanted", "hacktoberfest"),
    "advanced": ("help wanted", "hacktoberfest", "good first issue"),
}
STARTER_LABELS = {"good first issue", "good first issues", "first timers only", "beginner",
                  "easy", "starter", "first timer", "good first bug", "beginner friendly"}

STALE_ISSUE_DAYS = 548  # 18 months: older issues are dropped by vet anyway


# ---------------------------------------------------------------- profile


def normalise_name(name):
    name = re.sub(r"\s+", " ", str(name).strip().lower())
    name = "".join(ch for ch in name if ch not in '"\\:()')
    return ALIASES.get(name, name)


def lookup(name):
    """SkillSpec for a skill name. Unknown skills become keyword searches."""
    key = normalise_name(name)
    return CATALOG.get(key) or SkillSpec(key, "custom", (), key, ())


def normalise_profile(items):
    """[{"skill", "level"}] -> deduplicated, validated, capped list."""
    out, seen = [], set()
    for item in items:
        key = normalise_name(item.get("skill", ""))
        if not key or key in seen:
            continue
        level = str(item.get("level") or DEFAULT_LEVEL).lower()
        out.append({"skill": key, "level": level if level in LEVELS else DEFAULT_LEVEL})
        seen.add(key)
    return out[:MAX_SKILLS]


def parse_cli_profile(text):
    """"python:advanced,sql" -> profile list (level defaults to intermediate)."""
    items = []
    for part in text.split(","):
        name, _, level = part.partition(":")
        items.append({"skill": name, "level": level or DEFAULT_LEVEL})
    return normalise_profile(items)


def describe(profile):
    return ", ".join(f"{p['skill']} ({p['level']})" for p in profile)


# ---------------------------------------------------------------- matching


def _norm_label(label):
    return re.sub(r"[-_:]+", " ", label.lower()).strip()


def difficulty_from_labels(labels):
    """Best guess of the level an issue needs, from its labels alone."""
    normalised = {_norm_label(label) for label in labels}
    if normalised & STARTER_LABELS:
        return "beginner"
    if "help wanted" in normalised:
        return "intermediate"
    return None


def _mention(spec):
    words = [w for w in (spec.term or spec.key, spec.key, *spec.aliases) if w]
    alternatives = "|".join(re.escape(w) for w in sorted(set(words), key=len, reverse=True))
    return re.compile(rf"(?<![\w#+.-])(?:{alternatives})(?![\w#+])", re.I)


def match_skills(issue, profile):
    """Which of the contributor's skills this issue needs, with evidence.

    Strong evidence: the repo's language, a label, or the title.
    Weak evidence: a mention in the description, or only the search hit.
    Language skills never match on free-text mentions ("go", "c" and "r"
    appear in ordinary English).
    """
    labels = [_norm_label(label) for label in issue.get("labels", [])]
    title = issue.get("title", "")
    body = (issue.get("body") or "")[:6000]
    repo_language = issue.get("repo_language")
    found_by = set(issue.get("found_by", []))
    matches = []
    for p in profile:
        spec = lookup(p["skill"])
        strength, why = None, None
        if spec.kind == "language":
            if repo_language in spec.languages:
                strength, why = "strong", "repo language"
            elif spec.key in labels:
                strength, why = "strong", "label"
        else:
            pattern = _mention(spec)
            if any(pattern.fullmatch(label) for label in labels):
                strength, why = "strong", "label"
            elif pattern.search(title):
                strength, why = "strong", "title"
            elif pattern.search(body):
                strength, why = "weak", "description"
            elif spec.languages and repo_language in spec.languages and spec.key in found_by:
                strength, why = "weak", "repo language"
        if strength is None and spec.key in found_by:
            strength, why = "weak", "search match"
        if strength:
            matches.append({"skill": spec.key, "level": p["level"], "strength": strength, "why": why})
    matches.sort(key=lambda m: m["strength"] != "strong")
    return matches


# ---------------------------------------------------------------- search plan


@dataclass(frozen=True)
class PlannedQuery:
    skills: tuple        # skill keys this query serves
    terms: str           # qualifiers for the skill(s), without labels or base
    labels: tuple        # label set, OR-ed in advanced mode, one at a time in legacy mode
    legacy_terms: str    # same intent using only legacy-search syntax


def _base():
    since = (datetime.now(timezone.utc) - timedelta(days=STALE_ISSUE_DAYS)).date().isoformat()
    return f"is:issue is:open no:assignee archived:false created:>={since}"


def _merge_labels(*levels):
    out = []
    for level in levels:
        for label in LABELS_BY_LEVEL[level]:
            if label not in out:
                out.append(label)
    return tuple(out)


def _or(parts):
    return parts[0] if len(parts) == 1 else "(" + " OR ".join(parts) + ")"


def _language_terms(spec, advanced):
    langs = [f'language:"{lang}"' for lang in spec.languages]
    return _or(langs) if advanced else langs[0]


def _keyword_terms(spec):
    return f'"{spec.term or spec.key}" in:title,body'


def plan_queries(profile, max_combos=4):
    """One query per skill plus up to max_combos queries for pairs of skills
    that can be needed together: a language plus a framework of that
    language, or a language plus any tool or topic."""
    specs = [(lookup(p["skill"]), p["level"]) for p in profile]
    plan = []
    for spec, level in specs:
        if spec.kind == "language":
            plan.append(PlannedQuery((spec.key,), _language_terms(spec, True),
                                     LABELS_BY_LEVEL[level], _language_terms(spec, False)))
        else:
            plan.append(PlannedQuery((spec.key,), _keyword_terms(spec),
                                     LABELS_BY_LEVEL[level], _keyword_terms(spec)))

    combos = []
    for lang, lang_level in specs:
        if lang.kind != "language":
            continue
        for other, other_level in specs:
            if other.kind == "language":
                continue
            # Frameworks belong to an ecosystem (react is not in Python repos).
            # Topics and tools (sql, docker, tests, docs) appear in any repo.
            if other.kind == "framework" and not set(lang.languages) & set(other.languages):
                continue
            terms = f"{_language_terms(lang, True)} {_keyword_terms(other)}"
            legacy = f"{_language_terms(lang, False)} {_keyword_terms(other)}"
            # Lower level first: a sql beginner should not be steered to
            # "help wanted" issues because they are advanced in python.
            levels = sorted((lang_level, other_level), key=LEVELS.index)
            combos.append(PlannedQuery((lang.key, other.key), terms, _merge_labels(*levels), legacy))
    return plan + combos[:max_combos]


MAX_OPERATORS = 5  # GitHub search allows at most five AND/OR/NOT operators


def advanced_query(pq):
    """Labels OR-ed in one query, trimmed so the whole query stays within
    GitHub's operator limit (one operator is kept in reserve)."""
    used = pq.terms.count(" OR ")
    n_labels = max(1, MAX_OPERATORS - used)  # n labels need n-1 operators
    labels = _or([f'label:"{label}"' for label in pq.labels[:n_labels]])
    return f"{_base()} {labels} {pq.terms}"


def legacy_query(pq, label):
    return f'{_base()} label:"{label}" {pq.legacy_terms}'
