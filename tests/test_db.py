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
