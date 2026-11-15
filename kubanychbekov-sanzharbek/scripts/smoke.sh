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

# The demo accounts must exist. A fresh `docker compose up` has the schema but no data, so load the
# deterministic demo seed first (it is idempotent: repeating it adds nothing). Set SMOKE_SKIP_SEED=1
# to skip this when the system is already seeded or Docker is not used.
if [ -z "${SMOKE_SKIP_SEED:-}" ] && command -v docker >/dev/null 2>&1 && [ -f ../compose.yaml ]; then
  echo "smoke: loading demo seed (idempotent)"
  (cd .. && docker compose run --rm -T backend python -m app.seed) || echo "smoke: seeding failed, continuing" >&2
fi

exec "$PY" smoke.py
