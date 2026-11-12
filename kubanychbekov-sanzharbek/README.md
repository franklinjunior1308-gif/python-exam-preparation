# FixFlow

> Demo video: TODO (YouTube link goes here before submission)

Field-service management platform: Python/FastAPI + PostgreSQL backend, Next.js web, Flutter Android app.

## Status

Early stage. See [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) for what is and is not done.

## Requirements

Docker, `uv`, `bun`, Flutter SDK (with Android SDK).

## Run (backend + database)

```bash
cp .env.example .env
docker compose up --build
```

API: http://localhost:8000 (docs at `/docs`), readiness: `GET /api/v1/health/ready`.

## Checks

```bash
(cd backend && uv sync --frozen && uv run ruff check . && uv run ruff format --check . && uv run ty check . && uv run pytest -q)
```
