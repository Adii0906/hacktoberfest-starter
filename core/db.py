"""SQLite cache helpers. One file, three tables, no ORM."""

import json
import os
import sqlite3
import time

DB_PATH = os.path.join(os.getcwd(), "starter_cache.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS http_cache (key TEXT PRIMARY KEY, body TEXT, fetched_at INTEGER);
CREATE TABLE IF NOT EXISTS repo_cache (repo TEXT PRIMARY KEY, body TEXT, fetched_at INTEGER);
CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY, created_at INTEGER, payload TEXT);
"""


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


def cache_get(key, max_age_seconds):
    """Return the cached body for key if younger than max_age_seconds, else None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT body, fetched_at FROM http_cache WHERE key = ?", (key,)
        ).fetchone()
    if row is None or time.time() - row[1] > max_age_seconds:
        return None
    return json.loads(row[0])


def cache_set(key, body):
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO http_cache (key, body, fetched_at) VALUES (?, ?, ?)",
            (key, json.dumps(body), int(time.time())),
        )


def repo_get(repo, max_age_seconds):
    with _conn() as conn:
        row = conn.execute(
            "SELECT body, fetched_at FROM repo_cache WHERE repo = ?", (repo,)
        ).fetchone()
    if row is None or time.time() - row[1] > max_age_seconds:
        return None
    return json.loads(row[0])


def repo_set(repo, body):
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO repo_cache (repo, body, fetched_at) VALUES (?, ?, ?)",
            (repo, json.dumps(body), int(time.time())),
        )


def save_run(payload):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO runs (created_at, payload) VALUES (?, ?)",
            (int(time.time()), json.dumps(payload)),
        )


def load_latest_run():
    with _conn() as conn:
        row = conn.execute(
            "SELECT payload FROM runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return json.loads(row[0]) if row else None
