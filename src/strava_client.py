"""Small Strava HTTP client used by the app and processor.

This client is intentionally lightweight: it stores tokens via `src.db`
helpers and provides convenience methods for exchanging authorization codes,
refreshing tokens, listing activities and updating activity names.

Network calls use the `requests` library; tests patch `requests` to avoid
external HTTP requests.
"""

import time
import requests
from . import db


STRAVA_OAUTH_TOKEN = "https://www.strava.com/oauth/token"
API_BASE = "https://www.strava.com/api/v3"


class StravaClient:
    """Encapsulates Strava API operations required by the app.

    Args:
        client_id: Strava application client id (string).
        client_secret: Strava application client secret (string).
        db_path: path to the SQLite DB used by `src.db`.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        db_path: str,
        athlete_id: int = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.db_path = db_path
        self.athlete_id = athlete_id

    def exchange_code(self, code: str):
        """Exchange an OAuth `code` for tokens and persist them.

        Returns the parsed JSON response from Strava on success.
        """
        resp = requests.post(STRAVA_OAUTH_TOKEN, data={
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'grant_type': 'authorization_code'
        })
        resp.raise_for_status()
        data = resp.json()
        athlete = data.get('athlete') or {}
        self.athlete_id = db.save_tokens(
            self.db_path,
            data['access_token'],
            data['refresh_token'],
            data['expires_at'],
            athlete_id=athlete.get('id', self.athlete_id),
            first_name=athlete.get('firstname'),
        )
        return data

    def refresh_if_needed(self):
        """Refresh stored tokens when they're nearly expired.

        If no tokens are present this returns `None`. When a refresh occurs the
        new tokens are saved to the DB and returned.
        """
        tokens = db.get_tokens(self.db_path, self.athlete_id)
        if not tokens:
            return None
        # If token expires within 60 seconds, refresh
        if tokens['expires_at'] - int(time.time()) < 60:
            resp = requests.post(STRAVA_OAUTH_TOKEN, data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': tokens['refresh_token']
            })
            resp.raise_for_status()
            data = resp.json()
            db.save_tokens(
                self.db_path,
                data['access_token'],
                data['refresh_token'],
                data['expires_at'],
                athlete_id=self.athlete_id,
            )
            return data
        return tokens

    def _get_headers(self):
        """Return Authorization headers using stored access token.

        Raises RuntimeError when no tokens are stored.
        """
        tokens = db.get_tokens(self.db_path, self.athlete_id)
        if not tokens:
            raise RuntimeError('No tokens stored; complete OAuth first')
        return {'Authorization': f"Bearer {tokens['access_token']}"}

    def list_activities(self, after: int = None, per_page: int = 30):
        """Return a list of activities for the currently-authorized athlete.

        Args:
            after: optional epoch seconds; only activities after this time are returned.
            per_page: number of activities per page.
        """
        self.refresh_if_needed()
        params = {'per_page': per_page}
        if after:
            params['after'] = after
        resp = requests.get(f"{API_BASE}/athlete/activities", headers=self._get_headers(), params=params)
        if resp.status_code == 401:
            # token might have expired; attempt one refresh and retry
            self.refresh_if_needed()
            resp = requests.get(f"{API_BASE}/athlete/activities", headers=self._get_headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def get_activity_segment_names(self, activity_id: int, limit: int = 12):
        """Return unique segment names from an activity's detailed record."""
        self.refresh_if_needed()
        url = f"{API_BASE}/activities/{activity_id}"
        params = {'include_all_efforts': 'true'}
        resp = requests.get(url, headers=self._get_headers(), params=params)
        if resp.status_code == 401:
            self.refresh_if_needed()
            resp = requests.get(url, headers=self._get_headers(), params=params)
        resp.raise_for_status()

        names = []
        seen = set()
        for effort in resp.json().get('segment_efforts') or []:
            segment = effort.get('segment') or {}
            name = segment.get('name') or effort.get('name')
            if not isinstance(name, str):
                continue
            name = ' '.join(name.split()).strip()
            normalized = name.casefold()
            if not name or normalized in seen:
                continue
            seen.add(normalized)
            names.append(name[:100])
            if len(names) >= limit:
                break
        return names

    def update_activity_name(self, activity_id: int, new_name: str):
        """Update the name/title of an activity.

        Returns the parsed JSON response from Strava on success.
        """
        self.refresh_if_needed()
        resp = requests.put(f"{API_BASE}/activities/{activity_id}", headers=self._get_headers(), data={'name': new_name})
        if resp.status_code == 401:
            self.refresh_if_needed()
            resp = requests.put(f"{API_BASE}/activities/{activity_id}", headers=self._get_headers(), data={'name': new_name})
        resp.raise_for_status()
        return resp.json()
