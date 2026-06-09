"""Process new Strava activities and rename them.

This module contains the core business logic executed by the worker:
- read the last processed timestamp from `meta.last_processed`
- list new activities via the Strava API
- skip activities older than `NOT_BEFORE_DATE`
- rename remaining activities to a random Chinese title

Functions accept `db_path`/credentials so tests can call the logic in
isolation without relying on environment variables.
"""

import time
from datetime import datetime, timezone
from . import db
from .strava_client import StravaClient
from .chinese import random_chinese
import os


def process_new_activities(db_path: str = None, client_id: str = None, client_secret: str = None):
    """Process activities and return a tuple (updated, skipped).

    Args:
        db_path: path to the SQLite database.
        client_id: Strava client id override (for tests).
        client_secret: Strava client secret override (for tests).

    Returns:
        (updated_count, skipped_count)
    """
    db_path = db_path or os.getenv('DB_PATH')
    client_id = client_id or os.getenv('STRAVA_CLIENT_ID')
    client_secret = client_secret or os.getenv('STRAVA_CLIENT_SECRET')
    NOT_BEFORE = os.getenv('NOT_BEFORE_DATE', '2026-06-05')
    try:
        nb_dt = datetime.strptime(NOT_BEFORE, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        NOT_BEFORE_TS = int(nb_dt.timestamp())
    except Exception:
        NOT_BEFORE_TS = 0
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
        # start_date may be present as ISO string like 2026-06-05T12:34:56Z
        ts = None
        if 'start_date' in act:
            try:
                dt = datetime.strptime(act['start_date'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                ts = int(dt.timestamp())
            except Exception:
                ts = None
        if ts and ts > max_ts:
            max_ts = ts
        # skip activities before NOT_BEFORE date
        if ts is None or ts < NOT_BEFORE_TS:
            # log and continue; skipping is expected for old activities
            print(f"Skipping {act.get('id')} - before not-before date ({NOT_BEFORE})")
            skipped += 1
            continue
        title = random_chinese(6)
        try:
            client.update_activity_name(act['id'], title)
            updated += 1
        except Exception:
            # network or API errors should not stop processing other activities
            continue
    if max_ts:
        db.set_meta(db_path, 'last_processed', str(max_ts))
    return updated, skipped
