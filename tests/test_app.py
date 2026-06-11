from src import db
from src import app as app_module


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
    })

    assert response.status_code == 200
    assert b'preference has been saved' in response.data
    assert db.get_user(db_path, 88)['title_mode'] == 'chinese'

    response = client.get('/')
    assert b'href="/settings">Settings</a>' in response.data
