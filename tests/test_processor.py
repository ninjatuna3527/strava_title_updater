import tempfile
import os
from unittest.mock import patch
from src import db
from src.processor import process_new_activities


def make_activity(id, start_date):
    return {'id': id, 'start_date': start_date}


def test_processor_skips_before_not_before(tmp_path, monkeypatch):
    db_path = str(tmp_path / 'strava.db')
    db.init_db(db_path)
    # inject tokens so StravaClient won't fail on missing tokens
    db.save_tokens(db_path, 'a', 'r', 9999999)

    # supply activities: one before NOT_BEFORE (2026-06-01), one after (2026-07-01)
    acts = [make_activity(1, '2026-06-01T00:00:00Z'), make_activity(2, '2026-07-01T00:00:00Z')]

    class DummyClient:
        def __init__(self, *a, **k):
            pass

        def list_activities(self, after=None):
            return acts

        def update_activity_name(self, activity_id, new_name):
            return {'id': activity_id}

    with patch('src.processor.StravaClient', DummyClient):
        updated, skipped = process_new_activities(db_path=db_path, client_id='id', client_secret='sec')
        assert updated == 1
        assert skipped == 1
