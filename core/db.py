"""SQLite cache helpers. Singleton connection, WAL mode, three tables, no ORM.

The connection is created once per process and reused. WAL mode allows
concurrent reads from the Streamlit re-render while a background write
is in progress.
"""

import json
import os
import sqlite3
import threading
import time

DB_PATH = os.path.join(os.getcwd(), "starter_cache.db")

_lock = threading.RLock()  # re-entrant: writers hold it while _conn() may initialise
_conn_holder: dict = {}  # mutable holder so the closure can update it

_SCHEMA = """
CREATE TABLE IF NOT EXISTS http_cache (
    key        TEXT PRIMARY KEY,
    body       TEXT    NOT NULL,
    etag       TEXT,
    fetched_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS repo_cache (
    repo       TEXT PRIMARY KEY,
    body       TEXT    NOT NULL,
    fetched_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id         INTEGER PRIMARY KEY,
    created_at INTEGER NOT NULL,
    payload    TEXT    NOT NULL
);
"""


def _migrate(conn):
    """Bring cache files created by older versions up to the current schema."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(http_cache)")}
    if "etag" not in columns:
        conn.execute("ALTER TABLE http_cache ADD COLUMN etag TEXT")
        conn.commit()


def _conn() -> sqlite3.Connection:
    """Return the process-wide singleton connection, creating it on first use."""
    if "c" not in _conn_holder:
        with _lock:
            if "c" not in _conn_holder:
                conn = sqlite3.connect(DB_PATH, check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.executescript(_SCHEMA)
                _migrate(conn)
                _conn_holder["c"] = conn
    return _conn_holder["c"]


# ---------------------------------------------------------------- http_cache


def cache_get(key: str, max_age_seconds: int):
    """Return (body, etag) if the entry is fresh, else (None, stale_etag|None)."""
    row = _conn().execute(
        "SELECT body, etag, fetched_at FROM http_cache WHERE key = ?", (key,)
    ).fetchone()
    if row is None:
        return None, None
    body, etag, fetched_at = row
    if time.time() - fetched_at > max_age_seconds:
        # Stale but we can try a conditional request with the old ETag.
        return None, etag
    return json.loads(body), etag


def cache_set(key: str, body, etag: str | None = None):
    with _lock:
        _conn().execute(
            "INSERT OR REPLACE INTO http_cache (key, body, etag, fetched_at) VALUES (?, ?, ?, ?)",
            (key, json.dumps(body), etag, int(time.time())),
        )
        _conn().commit()


def cache_touch(key: str):
    """Bump fetched_at without changing body (used after a 304 Not Modified)."""
    with _lock:
        _conn().execute(
            "UPDATE http_cache SET fetched_at = ? WHERE key = ?",
            (int(time.time()), key),
        )
        _conn().commit()


# ---------------------------------------------------------------- repo_cache


def repo_get(repo: str, max_age_seconds: int):
    row = _conn().execute(
        "SELECT body, fetched_at FROM repo_cache WHERE repo = ?", (repo,)
    ).fetchone()
    if row is None or time.time() - row[1] > max_age_seconds:
        return None
    return json.loads(row[0])


def repo_set(repo: str, body):
    with _lock:
        _conn().execute(
            "INSERT OR REPLACE INTO repo_cache (repo, body, fetched_at) VALUES (?, ?, ?)",
            (repo, json.dumps(body), int(time.time())),
        )
        _conn().commit()


# ---------------------------------------------------------------- runs


def save_run(payload):
    with _lock:
        _conn().execute(
            "INSERT INTO runs (created_at, payload) VALUES (?, ?)",
            (int(time.time()), json.dumps(payload)),
        )
        _conn().commit()


def load_latest_run():
    row = _conn().execute(
        "SELECT payload FROM runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return json.loads(row[0]) if row else None


# ---------------------------------------------------------------- maintenance


def evict_stale(max_age_seconds: int = 24 * 60 * 60):
    """Remove http_cache entries older than max_age_seconds. Called lazily."""
    cutoff = int(time.time()) - max_age_seconds
    with _lock:
        _conn().execute("DELETE FROM http_cache WHERE fetched_at < ?", (cutoff,))
        _conn().commit()
