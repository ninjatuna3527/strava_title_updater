"""SQLite helpers for Strava users, tokens, settings, and processing state."""

import os
import sqlite3
from contextlib import contextmanager


DEFAULT_TITLE_MODE = "ai"
VALID_TITLE_MODES = {"ai", "chinese"}
DAILY_AI_TITLE_LIMIT = 20
COMMUTE_COLUMNS = (
    "commute_start_1",
    "commute_end_1",
    "commute_start_2",
    "commute_end_2",
)


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
                last_processed INTEGER,
                commute_start_1 TEXT,
                commute_end_1 TEXT,
                commute_start_2 TEXT,
                commute_end_2 TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_title_usage (
                athlete_id INTEGER NOT NULL,
                usage_date TEXT NOT NULL,
                title_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (athlete_id, usage_date)
            )
        """)
        existing_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(users)")
        }
        for column in COMMUTE_COLUMNS:
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE users ADD COLUMN {column} TEXT")

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
            SELECT athlete_id, first_name, title_mode, last_processed,
                   commute_start_1, commute_end_1,
                   commute_start_2, commute_end_2
            FROM users
            WHERE athlete_id = ?
        """, (int(athlete_id),)).fetchone()
    return dict(row) if row else None


def get_users(db_path: str):
    """Return every connected user."""
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute("""
            SELECT athlete_id, first_name, title_mode, last_processed,
                   commute_start_1, commute_end_1,
                   commute_start_2, commute_end_2
            FROM users
            ORDER BY athlete_id
        """).fetchall()
    return [dict(row) for row in rows]


def update_user_settings(
    db_path: str,
    athlete_id: int,
    title_mode: str,
    commute_start_1: str = None,
    commute_end_1: str = None,
    commute_start_2: str = None,
    commute_end_2: str = None,
):
    """Set title and commute-exclusion preferences for one athlete."""
    if title_mode not in VALID_TITLE_MODES:
        raise ValueError(f"Unsupported title mode: {title_mode}")
    commute_values = (
        commute_start_1,
        commute_end_1,
        commute_start_2,
        commute_end_2,
    )
    with _connect(db_path) as conn:
        result = conn.execute("""
            UPDATE users
            SET title_mode = ?,
                commute_start_1 = ?,
                commute_end_1 = ?,
                commute_start_2 = ?,
                commute_end_2 = ?
            WHERE athlete_id = ?
        """, (title_mode, *commute_values, int(athlete_id)))
        if result.rowcount == 0:
            raise KeyError(f"Unknown athlete: {athlete_id}")


def set_last_processed(db_path: str, athlete_id: int, timestamp: int):
    """Save the processing cursor for one athlete."""
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE users SET last_processed = ? WHERE athlete_id = ?",
            (int(timestamp), int(athlete_id)),
        )


def reserve_ai_title(
    db_path: str,
    athlete_id: int,
    usage_date: str,
    limit: int = DAILY_AI_TITLE_LIMIT,
):
    """Atomically reserve one daily AI title slot."""
    init_db(db_path)
    with _connect(db_path) as conn:
        result = conn.execute("""
            INSERT INTO ai_title_usage (athlete_id, usage_date, title_count)
            VALUES (?, ?, 1)
            ON CONFLICT(athlete_id, usage_date) DO UPDATE SET
                title_count = title_count + 1
            WHERE title_count < ?
        """, (int(athlete_id), usage_date, int(limit)))
        return result.rowcount == 1


def release_ai_title(db_path: str, athlete_id: int, usage_date: str):
    """Release a reserved slot after failed AI generation."""
    with _connect(db_path) as conn:
        conn.execute("""
            UPDATE ai_title_usage
            SET title_count = MAX(0, title_count - 1)
            WHERE athlete_id = ? AND usage_date = ?
        """, (int(athlete_id), usage_date))


def get_ai_title_usage(db_path: str, athlete_id: int, usage_date: str):
    """Return the number of AI titles generated for a user on a UTC date."""
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("""
            SELECT title_count
            FROM ai_title_usage
            WHERE athlete_id = ? AND usage_date = ?
        """, (int(athlete_id), usage_date)).fetchone()
    return row["title_count"] if row else 0


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
