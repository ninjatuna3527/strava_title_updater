"""Simple SQLite helpers for storing Strava tokens and small metadata.

This module provides a tiny, dependency-free interface used by the app and
worker. It intentionally keeps the schema minimal: a single tokens row (the
app stores only one active user/token pair) and a key/value `meta` table for
lightweight state like `last_processed` timestamps.

Functions are procedural and accept a `db_path` so tests can operate on
temporary database files.
"""

import sqlite3
import os


def init_db(db_path: str):
    """Create the SQLite database and required tables.

    Args:
        db_path: filesystem path where the SQLite file will be created.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tokens (
        id INTEGER PRIMARY KEY,
        access_token TEXT,
        refresh_token TEXT,
        expires_at INTEGER
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    conn.commit()
    conn.close()


def save_tokens(db_path: str, access_token: str, refresh_token: str, expires_at: int):
    """Store a single set of access/refresh tokens.

    The function deletes any existing tokens so the table contains at most one
    row. This design matches the single-user use-case of the app.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM tokens")
    cur.execute(
        "INSERT INTO tokens (access_token, refresh_token, expires_at) VALUES (?, ?, ?)",
        (access_token, refresh_token, expires_at),
    )
    conn.commit()
    conn.close()


def get_tokens(db_path: str):
    """Retrieve stored tokens.

    Returns a dict with keys `access_token`, `refresh_token`, and `expires_at`,
    or `None` when no tokens are stored.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT access_token, refresh_token, expires_at FROM tokens LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if row:
        return {"access_token": row[0], "refresh_token": row[1], "expires_at": row[2]}
    return None


def get_meta(db_path: str, key: str):
    """Get a string value from the `meta` table or `None` if missing."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT value FROM meta WHERE key=?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def set_meta(db_path: str, key: str, value: str):
    """Insert or update a key/value pair in the `meta` table."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()
