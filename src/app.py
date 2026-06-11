"""Flask web application providing OAuth flow and health endpoints.

The module exposes a small web UI to initiate the Strava OAuth flow and
contains `/health` and `/ready` endpoints suitable for container orchestration
health checks. The CLI also supports a `process` command to run the
processing step once (useful for debugging).
"""

import os
import sys
from flask import Flask, redirect, request, render_template, session, url_for
from dotenv import load_dotenv
from . import db
from .strava_client import StravaClient
from .processor import process_new_activities
import secrets
from werkzeug.middleware.proxy_fix import ProxyFix

DB_PATH = os.getenv('DB_PATH', './data/strava.db')
CLIENT_ID = os.getenv('STRAVA_CLIENT_ID')
CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET')
CALLBACK_HOSTNAME = os.getenv('CALLBACK_HOSTNAME')
CALLBACK_SCHEME = os.getenv('CALLBACK_SCHEME')
BASE_PATH = os.getenv('BASE_PATH', '')  # optional base path for reverse proxy setups (e.g. /stravaapps)

# Ensure Flask finds the top-level `templates/` directory when running as a module
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
templates_dir = os.path.join(root_dir, 'templates')
app = Flask(__name__, template_folder=templates_dir)
# secret key for session; prefer setting via FLASK_SECRET_KEY in environment
app.secret_key = os.getenv('FLASK_SECRET_KEY') or secrets.token_urlsafe(32)
app.config.update(
    SESSION_COOKIE_PATH=BASE_PATH or "/",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
db.init_db(DB_PATH)


@app.context_processor
def inject_base_path():
    """Expose `BASE_PATH` to templates so links can include the prefix."""
    return dict(BASE_PATH=BASE_PATH)


@app.route("/")
def index_page():
    athlete_id = session.get('athlete_id')
    user = db.get_user(DB_PATH, athlete_id) if athlete_id is not None else None
    return render_template("index.html", user=user)


@app.route('/authorize')
def authorize():
    """Redirect the user to the Strava authorization URL.

    A random `state` token is stored in the Flask session to mitigate CSRF.
    """
    client_id = os.getenv('STRAVA_CLIENT_ID') or CLIENT_ID
    callback_hostname = os.getenv('CALLBACK_HOSTNAME') or CALLBACK_HOSTNAME
    callback_scheme = os.getenv('CALLBACK_SCHEME') or CALLBACK_SCHEME or 'https'
    if not client_id:
        return 'Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in .env and restart.'
    if not callback_hostname:
        return 'Set CALLBACK_HOSTNAME in .env to the public hostname of this app (e.g. myapp.example.com) and restart.'
    if BASE_PATH is None:
        return 'Set BASE_PATH in .env to the base path this app is served under (e.g. /stravaapps) and restart.'
    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state
    # Allow overriding the public callback host (useful behind proxies/load
    # balancers). If CALLBACK_HOSTNAME is set, build redirect_uri from it and
    # optional CALLBACK_SCHEME; otherwise fall back to BASE_URL.
    # Build external redirect URI. If the application is served under a
    # reverse-proxy base path (e.g. /stravaapps) ensure the callback URI
    # includes that prefix so Strava redirects back correctly.
    if callback_hostname:
        redirect_uri = (
            f"{callback_scheme}://{callback_hostname}{BASE_PATH}/callback"
        )
    url = (
        f"https://www.strava.com/oauth/authorize?client_id={client_id}"
        f"&response_type=code&redirect_uri={redirect_uri}&approval_prompt=force&scope=activity:write,activity:read_all"
        f"&state={state}"
    )
    return redirect(url)


@app.route('/callback')
def callback():
    """Handle the OAuth callback and exchange the code for tokens."""
    code = request.args.get('code')
    state = request.args.get('state')
    if not code:
        return render_template(
            'callback.html',
            success=False,
            error_message='Authorization was denied or did not complete.',
        )
    saved = session.get('oauth_state')
    if not saved or state != saved:
        return render_template(
            'callback.html',
            success=False,
            error_message='The authorization request expired. Please try again.',
        ), 400
    client = StravaClient(
        os.getenv('STRAVA_CLIENT_ID') or CLIENT_ID,
        os.getenv('STRAVA_CLIENT_SECRET') or CLIENT_SECRET,
        DB_PATH,
    )
    data = client.exchange_code(code)
    athlete = data.get('athlete') or {}
    session.pop('oauth_state', None)
    session['athlete_id'] = client.athlete_id
    return render_template(
        'callback.html',
        success=True,
        first_name=athlete.get('firstname', ''),
    )


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Show and update settings for the connected Strava athlete."""
    athlete_id = session.get('athlete_id')
    if athlete_id is None:
        return redirect(f"{BASE_PATH}{url_for('authorize')}")

    user = db.get_user(DB_PATH, athlete_id)
    if not user:
        session.pop('athlete_id', None)
        return redirect(f"{BASE_PATH}{url_for('authorize')}")

    saved = False
    if request.method == 'POST':
        csrf_token = request.form.get('csrf_token')
        if not csrf_token or csrf_token != session.get('settings_csrf'):
            return ('Invalid settings request', 400)
        title_mode = request.form.get('title_mode', '')
        if title_mode not in db.VALID_TITLE_MODES:
            return ('Invalid title mode', 400)
        db.update_user_settings(DB_PATH, athlete_id, title_mode)
        user = db.get_user(DB_PATH, athlete_id)
        saved = True

    csrf_token = secrets.token_urlsafe(24)
    session['settings_csrf'] = csrf_token
    return render_template(
        'settings.html',
        user=user,
        csrf_token=csrf_token,
        saved=saved,
        ai_available=bool(os.getenv('OPENAI_API_KEY')),
    )


@app.route('/health')
def health():
    """Liveness probe: checks whether the DB file exists."""
    db_exists = os.path.exists(DB_PATH)
    return ('OK' if db_exists else 'DB MISSING', 200 if db_exists else 500)


@app.route('/ready')
def ready():
    """Readiness probe: DB exists and tokens are present."""
    if not os.path.exists(DB_PATH):
        return ('DB MISSING', 500)
    if not db.get_users(DB_PATH):
        return ('NO TOKENS', 500)
    return ('READY', 200)


if __name__ == '__main__':
    # simple CLI: `python -m src.app` runs server, `python -m src.app process` runs once
    if len(sys.argv) > 1 and sys.argv[1] == 'process':
        process_new_activities()
        sys.exit(0)
    db.init_db(DB_PATH)
    # Run the development server on plain HTTP. TLS is expected to be handled
    # by a reverse proxy (e.g., Nginx) in front of this application.
    app.run(host='0.0.0.0', port=5000)
