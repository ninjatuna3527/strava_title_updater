import time
from datetime import datetime, timezone
import requests
from . import db
from .strava_client import StravaClient
from .chinese import random_chinese
import os

DB_PATH = os.getenv('DB_PATH', './data/strava.db')
CLIENT_ID = os.getenv('STRAVA_CLIENT_ID')
CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET')
NOT_BEFORE = os.getenv('NOT_BEFORE_DATE', '2026-06-05')
try:
    nb_dt = datetime.strptime(NOT_BEFORE, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    NOT_BEFORE_TS = int(nb_dt.timestamp())
except Exception:
    NOT_BEFORE_TS = 0


def process_new_activities(db_path: str = None, client_id: str = None, client_secret: str = None):
    db_path = db_path or DB_PATH
    client_id = client_id or CLIENT_ID
    client_secret = client_secret or CLIENT_SECRET
    if not client_id or not client_secret:
        raise RuntimeError('STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET must be set')

    db.init_db(db_path)
    client = StravaClient(client_id, client_secret, db_path)
    last = db.get_meta(db_path, 'last_processed')
    after = int(last) if last else None
    activities = client.list_activities(after=after)
    if not activities:
        return 0, 0
    max_ts = after or 0
    updated = 0
    skipped = 0
    for act in activities:
        # start_date may be present as ISO string
        ts = None
        if 'start_date' in act:
            try:
                # Strava returns UTC Z timestamps like 2026-06-05T12:34:56Z
                # parse to UTC timestamp
                dt = datetime.strptime(act['start_date'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                ts = int(dt.timestamp())
            except Exception:
                ts = None
        if ts and ts > max_ts:
            max_ts = ts
        # skip activities before NOT_BEFORE date
        if ts is None or ts < NOT_BEFORE_TS:
            print(f"Skipping {act.get('id')} - before not-before date ({NOT_BEFORE})")
            skipped += 1
            continue
        title = random_chinese(6)
        try:
            client.update_activity_name(act['id'], title)
            updated += 1
        except Exception:
            continue
    if max_ts:
        db.set_meta(db_path, 'last_processed', str(max_ts))
    return updated, skipped
