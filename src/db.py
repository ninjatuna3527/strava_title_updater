"""SQLite helpers for Strava users, tokens, settings, and processing state."""

import os
import sqlite3
from contextlib import contextmanager


DEFAULT_TITLE_MODE = "ai"
VALID_TITLE_MODES = {"ai", "chinese"}


@contextmanager
def _connect(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str):
    """Create the database and migrate legacy single-user tokens."""
    directory = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(directory, exist_ok=True)

    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY,
                access_token TEXT,
                refresh_token TEXT,
                expires_at INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                athlete_id INTEGER PRIMARY KEY,
                first_name TEXT NOT NULL DEFAULT '',
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                title_mode TEXT NOT NULL DEFAULT 'ai',
                last_processed INTEGER
            )
        """)

        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        legacy = conn.execute("""
            SELECT access_token, refresh_token, expires_at
            FROM tokens
            ORDER BY id
            LIMIT 1
        """).fetchone()
        if user_count == 0 and legacy:
            last_processed = conn.execute(
                "SELECT value FROM meta WHERE key = 'last_processed'"
            ).fetchone()
            conn.execute("""
                INSERT INTO users (
                    athlete_id, access_token, refresh_token, expires_at,
                    title_mode, last_processed
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                0,
                legacy["access_token"],
                legacy["refresh_token"],
                legacy["expires_at"],
                DEFAULT_TITLE_MODE,
                int(last_processed["value"]) if last_processed else None,
            ))


def save_tokens(
    db_path: str,
    access_token: str,
    refresh_token: str,
    expires_at: int,
    athlete_id: int = None,
    first_name: str = None,
):
    """Insert or update tokens for one Strava athlete."""
    init_db(db_path)
    with _connect(db_path) as conn:
        if athlete_id is None:
            existing = conn.execute(
                "SELECT athlete_id FROM users ORDER BY athlete_id LIMIT 1"
            ).fetchone()
            athlete_id = existing["athlete_id"] if existing else 0

        conn.execute("""
            INSERT INTO users (
                athlete_id, first_name, access_token, refresh_token, expires_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(athlete_id) DO UPDATE SET
                first_name = CASE
                    WHEN excluded.first_name != '' THEN excluded.first_name
                    ELSE users.first_name
                END,
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_at = excluded.expires_at
        """, (
            int(athlete_id),
            (first_name or "").strip(),
            access_token,
            refresh_token,
            int(expires_at),
        ))
    return int(athlete_id)


def get_tokens(db_path: str, athlete_id: int = None):
    """Return tokens for an athlete, or the first stored user for compatibility."""
    init_db(db_path)
    with _connect(db_path) as conn:
        if athlete_id is None:
            row = conn.execute("""
                SELECT access_token, refresh_token, expires_at
                FROM users
                ORDER BY athlete_id
                LIMIT 1
            """).fetchone()
        else:
            row = conn.execute("""
                SELECT access_token, refresh_token, expires_at
                FROM users
                WHERE athlete_id = ?
            """, (int(athlete_id),)).fetchone()
    return dict(row) if row else None


def get_user(db_path: str, athlete_id: int):
    """Return a user's profile and settings."""
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("""
            SELECT athlete_id, first_name, title_mode, last_processed
            FROM users
            WHERE athlete_id = ?
        """, (int(athlete_id),)).fetchone()
    return dict(row) if row else None


def get_users(db_path: str):
    """Return every connected user."""
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute("""
            SELECT athlete_id, first_name, title_mode, last_processed
            FROM users
            ORDER BY athlete_id
        """).fetchall()
    return [dict(row) for row in rows]


def update_user_settings(db_path: str, athlete_id: int, title_mode: str):
    """Set the title generation mode for one athlete."""
    if title_mode not in VALID_TITLE_MODES:
        raise ValueError(f"Unsupported title mode: {title_mode}")
    with _connect(db_path) as conn:
        result = conn.execute(
            "UPDATE users SET title_mode = ? WHERE athlete_id = ?",
            (title_mode, int(athlete_id)),
        )
        if result.rowcount == 0:
            raise KeyError(f"Unknown athlete: {athlete_id}")


def set_last_processed(db_path: str, athlete_id: int, timestamp: int):
    """Save the processing cursor for one athlete."""
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE users SET last_processed = ? WHERE athlete_id = ?",
            (int(timestamp), int(athlete_id)),
        )


def get_meta(db_path: str, key: str):
    """Get a legacy global metadata value."""
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(db_path: str, key: str, value: str):
    """Set a legacy global metadata value."""
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (key, value),
        )
