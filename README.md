# Strava Chinese Title Updater

Small Flask app + scheduler that renames new Strava activities with random Chinese characters.

See .gitignore for exclusion of the .secure folder containing credentials.
# Chinese Title Strava

Small Python app that updates new Strava activities with titles containing random Chinese characters.

Local setup (Windows)

1. Create and activate a virtualenv (use Python 3.11+):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Configure environment:

```powershell
copy .env.example .env
# Edit .env and set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET
```
 
 Optionally set a Flask session secret to enable OAuth state protection (recommended):
 
 ```powershell
 # generate a secret and add to your .env or credentials file
 python - <<'PY'
 import secrets
 print(secrets.token_urlsafe(32))
 PY
 # then set FLASK_SECRET_KEY=the_value
 ```

4. Run the Flask server and complete OAuth:

```powershell
python -m src.app
# Visit http://localhost:5000/authorize and complete authorization
```

5. After authorization, process new activities once:

```powershell
python -m src.app process
```

Docker setup

Build the image and run with Docker:

```powershell
docker build -t chinese-title-strava .
docker run --rm -p 5000:5000 -e STRAVA_CLIENT_ID=YOUR_ID -e STRAVA_CLIENT_SECRET=YOUR_SECRET -v ${PWD}/data:/data chinese-title-strava
```

Or use `docker-compose` (preferred for local dev). Create a `.env` with `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET`, then:

```powershell
docker compose up --build
```

The app will be reachable at `http://localhost:5000`.

Notes

- Tokens and metadata are persisted to `/data/strava.db` inside the container. By default Compose mounts the host file `./.secure/strava.db` into the container at `/data/strava.db`.
- Keep your `STRAVA_CLIENT_SECRET` private; do not commit `.env` to version control.

Credentials file (secure mount)

You can keep secrets and the database outside `.env` in a directory that is mounted into the container at runtime. Create a local directory called `.secure/` and add a `credentials.txt` file with shell-style `KEY=VALUE` lines, for example:

```
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
# optional overrides
DB_PATH=/data/strava.db
BASE_URL=http://localhost:5000
```

Docker Compose is configured to mount the `./.secure` directory to `/app/.secure` inside the container and the container entrypoint will append its sanitized contents to `/app/.env` so the app can load them at startup. To avoid Compose warnings about missing variables, `docker-compose.yml` also uses `env_file: ./.secure/credentials.txt` so Compose will read and inject those variables when starting services.

Create or initialize the DB file before first run (Docker will create an empty file if it does not exist on Linux, but you may want to initialize permissions):

```powershell
mkdir .secure
# create an empty DB file or copy an existing one
if (-not (Test-Path ./.secure/strava.db)) { New-Item -Path ./.secure/strava.db -ItemType File }
```

Scheduler / periodic processing

- Default cutoff date: activities before `2026-06-05` are not updated. Configure with `NOT_BEFORE_DATE=YYYY-MM-DD`.
- The scheduler logs both updated and skipped activity counts. Example log line:

```
Processed activities, updated: 3, skipped: 5
```
