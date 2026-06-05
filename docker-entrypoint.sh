#!/bin/sh
set -e

# If credentials file exists, source it and export vars.
# Prefer /app/.secure/credentials.txt (directory mount), but keep compatibility
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

exec "$@"

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
