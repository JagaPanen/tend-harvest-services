#!/bin/sh
set -e

echo "Waiting for Postgres at ${DATABASE_HOST:-postgres}:5432..."
i=0
until python - <<'PY'
import os, socket, sys
host = os.environ.get("DATABASE_HOST", "postgres")
port = int(os.environ.get("DATABASE_PORT", "5432"))
try:
    with socket.create_connection((host, port), timeout=2):
        sys.exit(0)
except OSError:
    sys.exit(1)
PY
do
  i=$((i + 1))
  if [ "$i" -gt 60 ]; then
    echo "Postgres did not become ready in time"
    exit 1
  fi
  sleep 1
done

echo "Seeding demo org / catalog / template scenario..."
python -m app.seed

echo "Starting uvicorn on :8009"
exec uvicorn app.main:app --host 0.0.0.0 --port 8009 --proxy-headers
