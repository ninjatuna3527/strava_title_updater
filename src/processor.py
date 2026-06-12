"""Process new Strava activities for every connected user."""

from datetime import datetime, timezone
from . import db
from .strava_client import StravaClient
from .chinese import random_chinese
from .ai_titles import AITitleError, generate_ai_title
import os


class DailyTitleLimitError(RuntimeError):
    """Raised when a user has exhausted their daily AI title allowance."""


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
    updated = 0
    skipped = 0
    for user in db.get_users(db_path):
        user_updated, user_skipped = _process_user(
            user, db_path, client_id, client_secret, NOT_BEFORE_TS, NOT_BEFORE
        )
        updated += user_updated
        skipped += user_skipped
    return updated, skipped


def _process_user(user, db_path, client_id, client_secret, not_before_ts, not_before):
    client = StravaClient(
        client_id, client_secret, db_path, athlete_id=user['athlete_id']
    )
    after = user['last_processed']
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
        if ts is None or ts < not_before_ts:
            # log and continue; skipping is expected for old activities
            print(f"Skipping {act.get('id')} - before not-before date ({not_before})")
            skipped += 1
            continue
        if is_commute_activity(act, user):
            print(f"Skipping {act.get('id')} - inside a commute exclusion period")
            skipped += 1
            continue
        title = generate_activity_title(client, user, act, db_path=db_path)
        try:
            client.update_activity_name(act['id'], title)
            updated += 1
        except Exception:
            # network or API errors should not stop processing other activities
            continue
    if max_ts:
        db.set_last_processed(db_path, user['athlete_id'], max_ts)
    return updated, skipped


def generate_activity_title(client, user, activity, db_path=None):
    """Generate a title using the user's configured mode."""
    title = random_chinese(6)
    if user['title_mode'] != 'ai' or not os.getenv('OPENAI_API_KEY'):
        return title

    try:
        return generate_ai_activity_title(
            client,
            activity,
            db_path=db_path,
            athlete_id=user['athlete_id'],
        )
    except (AITitleError, DailyTitleLimitError) as exc:
        print(f"AI title generation failed for {activity.get('id')}: {exc}")
        return title


def generate_ai_activity_title(client, activity, db_path, athlete_id, now=None):
    """Generate an AI title for an activity, including segment context."""
    now = now or datetime.now(timezone.utc)
    usage_date = now.date().isoformat()
    if (
        db.get_ai_title_usage(db_path, athlete_id, usage_date)
        >= db.DAILY_AI_TITLE_LIMIT
    ):
        raise DailyTitleLimitError(
            f'Daily AI title limit of {db.DAILY_AI_TITLE_LIMIT} reached'
        )

    activity_context = dict(activity)
    segment_names = []
    try:
        details = client.get_activity_details(activity['id'])
        activity_context.update(details)
        segment_names = client.extract_segment_names(details)
    except Exception as exc:
        print(f"Activity detail lookup failed for {activity.get('id')}: {exc}")
    if not db.reserve_ai_title(db_path, athlete_id, usage_date):
        raise DailyTitleLimitError(
            f'Daily AI title limit of {db.DAILY_AI_TITLE_LIMIT} reached'
        )
    try:
        return generate_ai_title(
            activity_context.get('type')
            or activity_context.get('sport_type')
            or 'Activity',
            activity_context.get('elapsed_time', 0),
            activity_context.get('distance', 0),
            segment_names=segment_names,
            activity_metrics=activity_context,
        )
    except Exception:
        db.release_ai_title(db_path, athlete_id, usage_date)
        raise


def is_commute_activity(activity, user):
    """Return whether an activity starts inside a configured local-time window."""
    local_start = activity.get('start_date_local')
    if not local_start:
        return False
    try:
        activity_time = datetime.fromisoformat(
            local_start.replace('Z', '+00:00')
        ).time().replace(tzinfo=None)
    except (TypeError, ValueError):
        return False

    for number in (1, 2):
        start_value = user.get(f'commute_start_{number}')
        end_value = user.get(f'commute_end_{number}')
        if not start_value or not end_value:
            continue
        try:
            start = datetime.strptime(start_value, '%H:%M').time()
            end = datetime.strptime(end_value, '%H:%M').time()
        except ValueError:
            continue
        if start < end and start <= activity_time < end:
            return True
        if start > end and (activity_time >= start or activity_time < end):
            return True
    return False
