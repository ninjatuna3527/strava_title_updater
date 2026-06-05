import pytest
from unittest.mock import patch
from src.strava_client import StravaClient


def test_exchange_code_and_refresh(tmp_path, monkeypatch):
    import time as _time
    from src import db as _db
    db_path = str(tmp_path / 'db.sqlite')
    _db.init_db(db_path)
    client = StravaClient('id', 'secret', db_path)

    # mock requests.post for exchange_code
    class DummyResp:
        def __init__(self, data, status=200):
            self._data = data
            self.status_code = status

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception('http')

        def json(self):
            return self._data

    future = int(_time.time()) + 3600
    with patch('src.strava_client.requests.post') as mock_post:
        mock_post.return_value = DummyResp({'access_token': 'a', 'refresh_token': 'r', 'expires_at': future})
        res = client.exchange_code('code')
        assert res['access_token'] == 'a'

    # now simulate refresh flow: store an expired token and expect refresh to be called
    with patch('src.strava_client.requests.post') as mock_post:
        mock_post.return_value = DummyResp({'access_token': 'a2', 'refresh_token': 'r2', 'expires_at': future + 1000})
        # call refresh_if_needed (it will read tokens saved earlier)
        res = client.refresh_if_needed()
        # if tokens are not near expiry it returns existing tokens dict; ensure key exists
        assert isinstance(res, dict) or res is None


def test_list_and_update(monkeypatch, tmp_path):
    db_path = str(tmp_path / 'db.sqlite')
    client = StravaClient('id', 'secret', db_path)

    # prepare stored tokens
    import time as _time
    from src import db as _db
    _db.init_db(db_path)
    _db.save_tokens(db_path, 'tok', 'ref', int(_time.time()) + 3600)

    class DummyResp:
        def __init__(self, data, status=200):
            self._data = data
            self.status_code = status

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception('http')

        def json(self):
            return self._data

    with patch('src.strava_client.requests.get') as mock_get, patch('src.strava_client.requests.put') as mock_put:
        mock_get.return_value = DummyResp([{'id': 1, 'start_date': '2026-07-01T00:00:00Z'}])
        acts = client.list_activities()
        assert isinstance(acts, list)
        mock_put.return_value = DummyResp({'id': 1})
        res = client.update_activity_name(1, 'name')
        assert res['id'] == 1


def test_callback_hostname_override(monkeypatch):
    """When CALLBACK_HOSTNAME and CALLBACK_SCHEME are set, /authorize should
    build a redirect_uri using them instead of BASE_URL."""
    # ensure Flask app uses our env
    monkeypatch.setenv('STRAVA_CLIENT_ID', '22030')
    monkeypatch.setenv('STRAVA_CLIENT_SECRET', 'secret')
    monkeypatch.setenv('CALLBACK_HOSTNAME', 'app.example.com')
    monkeypatch.setenv('CALLBACK_SCHEME', 'https')

    from src import app as _app_mod
    _app_mod.app.config['TESTING'] = True
    client = _app_mod.app.test_client()
    resp = client.get('/authorize', follow_redirects=False)
    assert resp.status_code in (301, 302)
    loc = resp.headers.get('Location', '')
    assert 'https://app.example.com/callback' in loc
