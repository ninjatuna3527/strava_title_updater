from src import db
from src import app as app_module
from unittest.mock import patch


def test_settings_requires_connected_session(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'DB_PATH', str(tmp_path / 'strava.db'))
    app_module.app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)

    response = app_module.app.test_client().get('/settings')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/authorize')


def test_settings_shows_first_name_and_updates_title_mode(tmp_path, monkeypatch):
    db_path = str(tmp_path / 'strava.db')
    db.init_db(db_path)
    db.save_tokens(
        db_path, 'access', 'refresh', 9999999, athlete_id=88, first_name='Mei'
    )
    monkeypatch.setattr(app_module, 'DB_PATH', db_path)
    app_module.app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
    client = app_module.app.test_client()
    with client.session_transaction() as flask_session:
        flask_session['athlete_id'] = 88

    response = client.get('/settings')
    assert response.status_code == 200
    assert b'Hi, Mei.' in response.data

    with client.session_transaction() as flask_session:
        csrf_token = flask_session['settings_csrf']
    response = client.post('/settings', data={
        'csrf_token': csrf_token,
        'title_mode': 'chinese',
        'commute_start_1': '07:30',
        'commute_end_1': '09:00',
        'commute_start_2': '17:00',
        'commute_end_2': '19:00',
    })

    assert response.status_code == 200
    assert b'preference has been saved' in response.data
    assert db.get_user(db_path, 88)['title_mode'] == 'chinese'
    assert db.get_user(db_path, 88)['commute_start_1'] == '07:30'
    assert db.get_user(db_path, 88)['commute_end_2'] == '19:00'
    assert b'value="07:30"' in response.data

    response = client.get('/')
    assert b'href="/settings">Settings</a>' in response.data


def test_settings_rejects_incomplete_commute_period(tmp_path, monkeypatch):
    client = _connected_client(tmp_path, monkeypatch)
    client.get('/settings')
    with client.session_transaction() as flask_session:
        csrf_token = flask_session['settings_csrf']

    response = client.post('/settings', data={
        'csrf_token': csrf_token,
        'title_mode': 'ai',
        'commute_start_1': '07:30',
        'commute_end_1': '',
    })

    assert response.status_code == 400
    assert b'needs both a start and end time' in response.data


def _connected_client(tmp_path, monkeypatch, title_mode='ai'):
    db_path = str(tmp_path / 'strava.db')
    db.init_db(db_path)
    db.save_tokens(
        db_path, 'access', 'refresh', 9999999, athlete_id=88, first_name='Mei'
    )
    db.update_user_settings(db_path, 88, title_mode)
    monkeypatch.setattr(app_module, 'DB_PATH', db_path)
    app_module.app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
    client = app_module.app.test_client()
    with client.session_transaction() as flask_session:
        flask_session['athlete_id'] = 88
    return client


def test_activities_requires_connected_session(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'DB_PATH', str(tmp_path / 'strava.db'))
    app_module.app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)

    response = app_module.app.test_client().get('/activities')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/authorize')


def test_activities_lists_latest_ten(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    client = _connected_client(tmp_path, monkeypatch)
    calls = []

    class DummyStravaClient:
        def __init__(self, *args, **kwargs):
            assert kwargs['athlete_id'] == 88

        def list_activities(self, per_page=30):
            calls.append(per_page)
            return [{
                'id': 123,
                'name': 'Morning Run',
                'sport_type': 'Run',
                'distance': 5420,
                'elapsed_time': 1865,
                'start_date_local': '2026-06-11T07:30:00Z',
            }]

    with patch.object(app_module, 'StravaClient', DummyStravaClient):
        response = client.get('/activities')

    assert response.status_code == 200
    assert calls == [10]
    assert b'Morning Run' in response.data
    assert b'5.42 km' in response.data
    assert b'31m 05s' in response.data
    assert b'/activities/123/generate' in response.data
    assert b'Regenerate with AI' in response.data
    assert b'disabled' not in response.data
    assert b'20 of 20 AI titles remain today' in response.data


def test_generate_activity_name_updates_recent_activity(tmp_path, monkeypatch):
    client = _connected_client(tmp_path, monkeypatch, title_mode='chinese')
    updated = []
    activity = {
        'id': 123,
        'name': 'Morning Run',
        'type': 'Run',
        'distance': 5000,
        'elapsed_time': 1800,
    }

    class DummyStravaClient:
        def __init__(self, *args, **kwargs):
            pass

        def list_activities(self, per_page=30):
            assert per_page == 10
            return [activity]

        def update_activity_name(self, activity_id, title):
            updated.append((activity_id, title))

    with patch.object(app_module, 'StravaClient', DummyStravaClient):
        response = client.get('/activities')
        with client.session_transaction() as flask_session:
            csrf_token = flask_session['activities_csrf']
        with patch.object(
            app_module,
            'generate_ai_activity_title',
            return_value='The Hill Started It',
        ) as generate:
            response = client.post(
                '/activities/123/generate',
                data={'csrf_token': csrf_token},
                follow_redirects=True,
            )

    assert response.status_code == 200
    generate.assert_called_once()
    assert updated == [(123, 'The Hill Started It')]
    assert b'Activity renamed to' in response.data
    assert b'The Hill Started It' in response.data


def test_generate_activity_name_reports_daily_limit(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    client = _connected_client(tmp_path, monkeypatch)

    class DummyStravaClient:
        def __init__(self, *args, **kwargs):
            pass

        def list_activities(self, per_page=30):
            return [{'id': 123, 'type': 'Run'}]

    with patch.object(app_module, 'StravaClient', DummyStravaClient):
        client.get('/activities')
        with client.session_transaction() as flask_session:
            csrf_token = flask_session['activities_csrf']
        with patch.object(
            app_module,
            'generate_ai_activity_title',
            side_effect=app_module.DailyTitleLimitError('limit'),
        ):
            response = client.post(
                '/activities/123/generate',
                data={'csrf_token': csrf_token},
                follow_redirects=True,
            )

    assert response.status_code == 200
    assert b'daily limit of 20 AI titles has been reached' in response.data


def test_generate_activity_name_rejects_non_recent_activity(tmp_path, monkeypatch):
    client = _connected_client(tmp_path, monkeypatch)

    class DummyStravaClient:
        def __init__(self, *args, **kwargs):
            pass

        def list_activities(self, per_page=30):
            return [{'id': 123}]

    with patch.object(app_module, 'StravaClient', DummyStravaClient):
        client.get('/activities')
        with client.session_transaction() as flask_session:
            csrf_token = flask_session['activities_csrf']
        response = client.post(
            '/activities/999/generate',
            data={'csrf_token': csrf_token},
        )

    assert response.status_code == 404
