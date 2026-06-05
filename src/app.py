"""Flask web application providing OAuth flow and health endpoints.

The module exposes a small web UI to initiate the Strava OAuth flow and
contains `/health` and `/ready` endpoints suitable for container orchestration
health checks. The CLI also supports a `process` command to run the
processing step once (useful for debugging).
"""

import os
import sys
from flask import Flask, redirect, request, render_template, session
from dotenv import load_dotenv
from . import db
from .strava_client import StravaClient
from .processor import process_new_activities
import secrets


load_dotenv()


DB_PATH = os.getenv('DB_PATH', './data/strava.db')
CLIENT_ID = os.getenv('STRAVA_CLIENT_ID')
CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET')
# BASE_URL is a full URL used as a fallback. Prefer configuring a hostname
# via CALLBACK_HOSTNAME for environments where the public host differs from
# the container's perceived host (load balancers, proxies, etc.).
BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')
CALLBACK_HOSTNAME = os.getenv('CALLBACK_HOSTNAME')
CALLBACK_SCHEME = os.getenv('CALLBACK_SCHEME')
BASE_PATH = os.getenv('BASE_PATH', '')

# Ensure Flask finds the top-level `templates/` directory when running as a module
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
templates_dir = os.path.join(root_dir, 'templates')
app = Flask(__name__, template_folder=templates_dir)
# secret key for session; prefer setting via FLASK_SECRET_KEY in environment
app.secret_key = os.getenv('FLASK_SECRET_KEY') or secrets.token_urlsafe(32)


@app.context_processor
def inject_base_path():
    """Expose `BASE_PATH` to templates so links can include the prefix."""
    return dict(BASE_PATH=BASE_PATH)


@app.route('/')
def index():
    """Render the small landing page that starts OAuth."""
    return render_template('login.html')


@app.route('/authorize')
def authorize():
    """Redirect the user to the Strava authorization URL.

    A random `state` token is stored in the Flask session to mitigate CSRF.
    """
    if not CLIENT_ID:
        return 'Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in .env and restart.'
    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state
    # Allow overriding the public callback host (useful behind proxies/load
    # balancers). If CALLBACK_HOSTNAME is set, build redirect_uri from it and
    # optional CALLBACK_SCHEME; otherwise fall back to BASE_URL.
    # Build external redirect URI. If the application is served under a
    # reverse-proxy base path (e.g. /stravaapps) ensure the callback URI
    # includes that prefix so Strava redirects back correctly.
    if CALLBACK_HOSTNAME:
        scheme = CALLBACK_SCHEME or ('https' if BASE_URL.startswith('https') else 'http')
        redirect_uri = f"{scheme}://{CALLBACK_HOSTNAME}{BASE_PATH}/callback"
    else:
        redirect_uri = f"{BASE_URL}{BASE_PATH}/callback"
    url = (
        f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}"
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
        return 'Authorization failed or denied.'
    saved = session.get('oauth_state')
    if not saved or state != saved:
        return ('Invalid or missing OAuth state', 400)
    client = StravaClient(CLIENT_ID, CLIENT_SECRET, DB_PATH)
    client.exchange_code(code)
    return render_template('callback.html')


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
    tokens = db.get_tokens(DB_PATH)
    if not tokens:
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
