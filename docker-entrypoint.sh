#!/bin/sh
set -e

# Load credentials from Docker secrets when available. Docker places secrets
# at /run/secrets/<name>. Support both a combined secret file named
# `strava_credentials` (containing KEY=VALUE lines) and individual secrets
# `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` as separate files.
if [ -f /run/secrets/strava_credentials ]; then
  SAN=/tmp/credentials.sanitized
  sed 's/\r$//' /run/secrets/strava_credentials > "$SAN"
  set -a
  . "$SAN"
  set +a
  if [ -w /app/.env ] || [ ! -e /app/.env ]; then
    grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$SAN" >> /app/.env || true
  fi
fi

# Load individual secret files if present
if [ -f /run/secrets/STRAVA_CLIENT_ID ]; then
  export STRAVA_CLIENT_ID=$(sed 's/\r$//' /run/secrets/STRAVA_CLIENT_ID)
  echo "STRAVA_CLIENT_ID=${STRAVA_CLIENT_ID}" >> /app/.env || true
fi
if [ -f /run/secrets/STRAVA_CLIENT_SECRET ]; then
  export STRAVA_CLIENT_SECRET=$(sed 's/\r$//' /run/secrets/STRAVA_CLIENT_SECRET)
  echo "STRAVA_CLIENT_SECRET=${STRAVA_CLIENT_SECRET}" >> /app/.env || true
fi

# SSL/TLS certificate handling removed: TLS is expected to be terminated by
# the reverse proxy (Nginx). Do not set SSL_CERTFILE/SSL_KEYFILE in this
# container; manage certificates at the proxy level.

# If credentials file exists, source it and export vars.
# Prefer /app/.secure/credentials.txt (directory mount).
# with the previous /app.secure/credentials.txt path.
if [ -f /app/.secure/credentials.txt ]; then
  # sanitize CRLF and comments, export variables, and append safe lines to /app/.env
  SAN=/tmp/credentials.sanitized
  sed 's/\r$//' /app/.secure/credentials.txt > "$SAN"
  # export valid KEY=VALUE lines (ignore comments/blank lines)
  set -a
  # shellcheck disable=SC1090
  . "$SAN"
  set +a
  # append only valid env lines to /app/.env
  if [ -w /app/.env ] || [ ! -e /app/.env ]; then
    grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$SAN" >> /app/.env || true
  fi
fi

# If GUNICORN_WORKERS is not set, compute a sensible default: (2 * CPU) + 1
if [ -z "$GUNICORN_WORKERS" ]; then
  if command -v nproc >/dev/null 2>&1; then
    CPUS=$(nproc)
  elif [ -f /proc/cpuinfo ]; then
    CPUS=$(grep -c ^processor /proc/cpuinfo)
  else
    CPUS=1
  fi
  export GUNICORN_WORKERS=$((2 * CPUS + 1))
fi

exec "$@"
