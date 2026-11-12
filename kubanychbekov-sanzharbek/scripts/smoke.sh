#!/usr/bin/env bash
# Smoke test against a running, seeded system. Non-zero exit on any unexpected result.
set -euo pipefail
API="${API_URL:-http://localhost:8000}/api/v1"

code=$(curl -s -o /dev/null -w '%{http_code}' "$API/health/ready")
[ "$code" = "200" ] || { echo "FAIL: readiness returned $code"; exit 1; }
echo "ok: readiness"

# TODO: login, create request, assign, expect 409 on conflict (added with the domain code).
echo "smoke: only health checked so far"
