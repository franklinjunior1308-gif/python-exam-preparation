#!/usr/bin/env bash
# Smoke test against a running, seeded system (docker compose up -d; python -m app.seed). Non-zero exit on failure.
set -euo pipefail
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python)"
exec "$PY" smoke.py
