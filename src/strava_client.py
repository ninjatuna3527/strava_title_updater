import time
import requests
from . import db

STRAVA_OAUTH_TOKEN = "https://www.strava.com/oauth/token"
API_BASE = "https://www.strava.com/api/v3"

class StravaClient:
    def __init__(self, client_id: str, client_secret: str, db_path: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.db_path = db_path

    def exchange_code(self, code: str):
        resp = requests.post(STRAVA_OAUTH_TOKEN, data={
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'grant_type': 'authorization_code'
        })
        resp.raise_for_status()
        data = resp.json()
        db.save_tokens(self.db_path, data['access_token'], data['refresh_token'], data['expires_at'])
        return data

    def refresh_if_needed(self):
        tokens = db.get_tokens(self.db_path)
        if not tokens:
            return None
        if tokens['expires_at'] - int(time.time()) < 60:
            resp = requests.post(STRAVA_OAUTH_TOKEN, data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': tokens['refresh_token']
            })
            resp.raise_for_status()
            data = resp.json()
            db.save_tokens(self.db_path, data['access_token'], data['refresh_token'], data['expires_at'])
            return data
        return tokens

    def _get_headers(self):
        tokens = db.get_tokens(self.db_path)
        if not tokens:
            raise RuntimeError('No tokens stored; complete OAuth first')
        return {'Authorization': f"Bearer {tokens['access_token']}"}

    def list_activities(self, after: int = None, per_page: int = 30):
        self.refresh_if_needed()
        params = {'per_page': per_page}
        if after:
            params['after'] = after
        resp = requests.get(f"{API_BASE}/athlete/activities", headers=self._get_headers(), params=params)
        if resp.status_code == 401:
            self.refresh_if_needed()
            resp = requests.get(f"{API_BASE}/athlete/activities", headers=self._get_headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def update_activity_name(self, activity_id: int, new_name: str):
        self.refresh_if_needed()
        resp = requests.put(f"{API_BASE}/activities/{activity_id}", headers=self._get_headers(), data={'name': new_name})
        if resp.status_code == 401:
            self.refresh_if_needed()
            resp = requests.put(f"{API_BASE}/activities/{activity_id}", headers=self._get_headers(), data={'name': new_name})
        resp.raise_for_status()
        return resp.json()
