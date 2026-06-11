import tempfile
import os
from src import db


def test_db_init_and_tokens_and_meta():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, 'strava.db')
        db.init_db(path)
        # initially no tokens
        assert db.get_tokens(path) is None
        db.save_tokens(path, 'a', 'r', 123456)
        t = db.get_tokens(path)
        assert t['access_token'] == 'a'
        assert t['refresh_token'] == 'r'
        assert t['expires_at'] == 123456
        assert db.get_meta(path, 'nonexistent') is None
        db.set_meta(path, 'last_processed', '100')
        assert db.get_meta(path, 'last_processed') == '100'


def test_users_store_profile_settings_and_tokens_independently(tmp_path):
    path = str(tmp_path / 'strava.db')
    db.init_db(path)

    db.save_tokens(path, 'a1', 'r1', 123, athlete_id=11, first_name='Ada')
    db.save_tokens(path, 'a2', 'r2', 456, athlete_id=22, first_name='Grace')
    db.update_user_settings(path, 22, 'chinese')

    assert db.get_tokens(path, 11)['access_token'] == 'a1'
    assert db.get_tokens(path, 22)['access_token'] == 'a2'
    assert db.get_user(path, 11)['first_name'] == 'Ada'
    assert db.get_user(path, 11)['title_mode'] == 'ai'
    assert db.get_user(path, 22)['title_mode'] == 'chinese'
    assert len(db.get_users(path)) == 2


def test_init_db_migrates_legacy_tokens_and_cursor(tmp_path):
    import sqlite3

    path = str(tmp_path / 'legacy.db')
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE tokens (
                id INTEGER PRIMARY KEY,
                access_token TEXT,
                refresh_token TEXT,
                expires_at INTEGER
            )
        """)
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "INSERT INTO tokens (access_token, refresh_token, expires_at) VALUES (?, ?, ?)",
            ('legacy-a', 'legacy-r', 789),
        )
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('last_processed', '321')"
        )

    db.init_db(path)

    user = db.get_user(path, 0)
    assert user['last_processed'] == 321
    assert db.get_tokens(path, 0)['access_token'] == 'legacy-a'
