import os
import sys
import time
from flask import Flask, redirect, request, render_template, session
from dotenv import load_dotenv
from . import db
from .strava_client import StravaClient
from .chinese import random_chinese
from .processor import process_new_activities
import os
import secrets

load_dotenv()

DB_PATH = os.getenv('DB_PATH', './data/strava.db')
CLIENT_ID = os.getenv('STRAVA_CLIENT_ID')
CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET')
BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')

# Ensure Flask finds the top-level `templates/` directory when running as a module
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
templates_dir = os.path.join(root_dir, 'templates')
app = Flask(__name__, template_folder=templates_dir)
# secret key for session; prefer setting via FLASK_SECRET_KEY in environment
app.secret_key = os.getenv('FLASK_SECRET_KEY') or secrets.token_urlsafe(32)

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/authorize')
def authorize():
    if not CLIENT_ID:
        return 'Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in .env and restart.'
    # generate and store OAuth state to protect against CSRF
    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state
    redirect_uri = f"{BASE_URL}/callback"
    url = (
        f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}"
        f"&response_type=code&redirect_uri={redirect_uri}&approval_prompt=force&scope=activity:write,activity:read_all"
        f"&state={state}"
    )
    return redirect(url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    state = request.args.get('state')
    if not code:
        return 'Authorization failed or denied.'
    # verify state matches
    saved = session.get('oauth_state')
    if not saved or state != saved:
        return ('Invalid or missing OAuth state', 400)
    client = StravaClient(CLIENT_ID, CLIENT_SECRET, DB_PATH)
    client.exchange_code(code)
    return render_template('callback.html')


@app.route('/health')
def health():
    # basic health: can we access the DB (file exists)
    db_exists = os.path.exists(DB_PATH)
    return ('OK' if db_exists else 'DB MISSING', 200 if db_exists else 500)


@app.route('/ready')
def ready():
    # readiness: DB exists and tokens present
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
    app.run(host='0.0.0.0', port=5000)
