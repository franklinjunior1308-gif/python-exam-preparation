#!/usr/bin/env bash
# Runs backend, web and mobile checks; fails on the first error.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== backend =="
if [ "${BACKEND_TESTS_IN_DOCKER:-0}" = "1" ]; then
  # For machines where native Python wheels are blocked (Windows Smart App Control): static checks run on the
  # host, the test suite runs in the backend image against PostgreSQL.
  (cd backend && uv sync --frozen && uv run ruff check . && uv run ruff format --check . && uv run ty check .)
  docker compose --profile test run --rm backend-tests
else
  (cd backend && uv sync --frozen && uv run ruff check . && uv run ruff format --check . \
    && uv run ty check . && uv run pytest -q)
fi

if [ -f web/package.json ]; then
  echo "== web =="
  (cd web && bun install --frozen-lockfile && bun run lint && bun run typecheck \
    && bun run test:ci && bun run build)
else
  echo "web: not implemented yet" >&2; exit 1
fi

if [ -f mobile/pubspec.yaml ]; then
  echo "== mobile =="
  (cd mobile && flutter pub get && dart format --output=none --set-exit-if-changed lib test \
    && flutter analyze && flutter test && flutter build apk --debug)
else
  echo "mobile: not implemented yet" >&2; exit 1
fi

echo "ALL CHECKS PASSED"
