#!/usr/bin/env bash
# Smoke test against a running, seeded system (docker compose up -d; python -m app.seed). Non-zero exit on failure.
set -euo pipefail
cd "$(dirname "$0")"

# Pick an interpreter that really runs: on Windows `python3` may be the Microsoft Store shim.
PY=""
for candidate in python3 python py; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import sys" >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "smoke: no working Python 3 interpreter found" >&2
  exit 2
fi
exec "$PY" smoke.py
