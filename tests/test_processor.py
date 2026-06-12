import tempfile
import os
from unittest.mock import patch
from src import db
from src.ai_titles import AITitleError
from src.processor import (
    DailyTitleLimitError,
    generate_ai_activity_title,
    is_commute_activity,
    process_new_activities,
)


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
        'average_speed': 2.5,
    }]
    updated_names = []

    class DummyClient:
        def __init__(self, *a, **k):
            pass

        def list_activities(self, after=None):
            return acts

        def get_activity_details(self, activity_id):
            assert activity_id == 3
            return {
                'calories': 420,
                'total_elevation_gain': 125,
                'segment_efforts': [
                    {'segment': {'name': 'Park Climb'}},
                    {'segment': {'name': 'River Sprint'}},
                ],
            }

        def extract_segment_names(self, activity):
            return [
                effort['segment']['name']
                for effort in activity['segment_efforts']
            ]

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

    generate.assert_called_once_with(
        'Run',
        1800,
        5000,
        segment_names=['Park Climb', 'River Sprint'],
        activity_metrics={
            'id': 3,
            'start_date': '2026-07-01T00:00:00Z',
            'type': 'Run',
            'elapsed_time': 1800,
            'distance': 5000,
            'average_speed': 2.5,
            'calories': 420,
            'total_elevation_gain': 125,
            'segment_efforts': [
                {'segment': {'name': 'Park Climb'}},
                {'segment': {'name': 'River Sprint'}},
            ],
        },
    )
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


def test_processor_uses_chinese_mode_even_when_ai_is_configured(tmp_path, monkeypatch):
    db_path = str(tmp_path / 'strava.db')
    db.init_db(db_path)
    db.save_tokens(
        db_path, 'a', 'r', 9999999, athlete_id=7, first_name='Lin'
    )
    db.update_user_settings(db_path, 7, 'chinese')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    acts = [make_activity(5, '2026-07-01T00:00:00Z')]
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
        patch('src.processor.random_chinese', return_value='characters'),
        patch('src.processor.generate_ai_title') as generate,
    ):
        result = process_new_activities(
            db_path=db_path, client_id='id', client_secret='sec'
        )

    generate.assert_not_called()
    assert updated_names == ['characters']
    assert result == (1, 0)


def test_processor_skips_activity_in_commute_period(tmp_path):
    db_path = str(tmp_path / 'strava.db')
    db.init_db(db_path)
    db.save_tokens(db_path, 'a', 'r', 9999999, athlete_id=7)
    db.update_user_settings(
        db_path,
        7,
        'chinese',
        commute_start_1='07:30',
        commute_end_1='09:00',
    )
    acts = [{
        'id': 6,
        'start_date': '2026-07-01T07:45:00Z',
        'start_date_local': '2026-07-01T08:45:00Z',
    }]
    updated_names = []

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def list_activities(self, after=None):
            return acts

        def update_activity_name(self, activity_id, new_name):
            updated_names.append(new_name)

    with patch('src.processor.StravaClient', DummyClient):
        result = process_new_activities(
            db_path=db_path, client_id='id', client_secret='sec'
        )

    assert updated_names == []
    assert result == (0, 1)


def test_commute_period_matching_supports_overnight_and_end_boundary():
    user = {
        'commute_start_1': '22:00',
        'commute_end_1': '06:00',
        'commute_start_2': '07:30',
        'commute_end_2': '09:00',
    }

    assert is_commute_activity(
        {'start_date_local': '2026-07-01T23:15:00Z'}, user
    )
    assert is_commute_activity(
        {'start_date_local': '2026-07-02T05:59:00Z'}, user
    )
    assert is_commute_activity(
        {'start_date_local': '2026-07-02T07:30:00Z'}, user
    )
    assert not is_commute_activity(
        {'start_date_local': '2026-07-02T06:00:00Z'}, user
    )
    assert not is_commute_activity(
        {'start_date_local': '2026-07-02T09:00:00Z'}, user
    )


def test_ai_generation_releases_quota_after_failure(tmp_path):
    from datetime import datetime, timezone

    db_path = str(tmp_path / 'strava.db')
    db.init_db(db_path)

    class DummyClient:
        def get_activity_details(self, activity_id):
            return {}

        def extract_segment_names(self, activity):
            return []

    now = datetime(2026, 6, 11, tzinfo=timezone.utc)
    with patch(
        'src.processor.generate_ai_title',
        side_effect=AITitleError('service unavailable'),
    ):
        try:
            generate_ai_activity_title(
                DummyClient(),
                {'id': 1, 'type': 'Run'},
                db_path=db_path,
                athlete_id=7,
                now=now,
            )
        except AITitleError:
            pass

    assert db.get_ai_title_usage(db_path, 7, '2026-06-11') == 0


def test_ai_generation_rejects_twenty_first_title(tmp_path):
    from datetime import datetime, timezone

    db_path = str(tmp_path / 'strava.db')
    db.init_db(db_path)
    for _ in range(20):
        db.reserve_ai_title(db_path, 7, '2026-06-11')

    with patch('src.processor.generate_ai_title') as generate:
        try:
            generate_ai_activity_title(
                object(),
                {'id': 1, 'type': 'Run'},
                db_path=db_path,
                athlete_id=7,
                now=datetime(2026, 6, 11, tzinfo=timezone.utc),
            )
            assert False, 'Expected the daily title limit to be enforced'
        except DailyTitleLimitError:
            pass

    generate.assert_not_called()


def test_processor_falls_back_to_chinese_after_daily_ai_limit(
    tmp_path, monkeypatch
):
    from datetime import datetime, timezone

    db_path = str(tmp_path / 'strava.db')
    db.init_db(db_path)
    db.save_tokens(db_path, 'a', 'r', 9999999, athlete_id=7)
    usage_date = datetime.now(timezone.utc).date().isoformat()
    for _ in range(20):
        db.reserve_ai_title(db_path, 7, usage_date)
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    acts = [make_activity(8, '2026-07-01T10:00:00Z')]
    updated_names = []

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def list_activities(self, after=None):
            return acts

        def update_activity_name(self, activity_id, new_name):
            updated_names.append(new_name)

    with (
        patch('src.processor.StravaClient', DummyClient),
        patch('src.processor.random_chinese', return_value='quota fallback'),
        patch('src.processor.generate_ai_title') as generate,
    ):
        result = process_new_activities(
            db_path=db_path, client_id='id', client_secret='sec'
        )

    generate.assert_not_called()
    assert updated_names == ['quota fallback']
    assert result == (1, 0)
