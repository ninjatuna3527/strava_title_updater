import tempfile
import os
from unittest.mock import patch
from src import db
from src.ai_titles import AITitleError
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


def test_processor_uses_activity_details_for_ai_title(tmp_path, monkeypatch):
    db_path = str(tmp_path / 'strava.db')
    db.init_db(db_path)
    db.save_tokens(db_path, 'a', 'r', 9999999)
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    acts = [{
        'id': 3,
        'start_date': '2026-07-01T00:00:00Z',
        'type': 'Run',
        'elapsed_time': 1800,
        'distance': 5000,
    }]
    updated_names = []

    class DummyClient:
        def __init__(self, *a, **k):
            pass

        def list_activities(self, after=None):
            return acts

        def update_activity_name(self, activity_id, new_name):
            updated_names.append((activity_id, new_name))
            return {'id': activity_id}

    with (
        patch('src.processor.StravaClient', DummyClient),
        patch(
            'src.processor.generate_ai_title',
            return_value='I Was Saving Energy for Later',
        ) as generate,
    ):
        updated, skipped = process_new_activities(
            db_path=db_path, client_id='id', client_secret='sec'
        )

    generate.assert_called_once_with('Run', 1800, 5000)
    assert updated_names == [(3, 'I Was Saving Energy for Later')]
    assert (updated, skipped) == (1, 0)


def test_processor_falls_back_when_ai_generation_fails(tmp_path, monkeypatch):
    db_path = str(tmp_path / 'strava.db')
    db.init_db(db_path)
    db.save_tokens(db_path, 'a', 'r', 9999999)
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    acts = [make_activity(4, '2026-07-01T00:00:00Z')]
    updated_names = []

    class DummyClient:
        def __init__(self, *a, **k):
            pass

        def list_activities(self, after=None):
            return acts

        def update_activity_name(self, activity_id, new_name):
            updated_names.append(new_name)

    with (
        patch('src.processor.StravaClient', DummyClient),
        patch('src.processor.random_chinese', return_value='fallback'),
        patch(
            'src.processor.generate_ai_title',
            side_effect=AITitleError('service unavailable'),
        ),
    ):
        updated, skipped = process_new_activities(
            db_path=db_path, client_id='id', client_secret='sec'
        )

    assert updated_names == ['fallback']
    assert (updated, skipped) == (1, 0)
