# Verification log

What was actually run, and what happened. Updated as work progresses. Date: 2026-11-12.

## Backend (Docker, PostgreSQL 17)
```bash
docker compose --profile test run --rm backend-tests
```
Result: `ruff check` passed, **140 passed, 0 failed, 0 skipped** (pytest 9.2). The set includes the
97 lifecycle tests, 19 scheduling-rule tests, 2 health tests and 22 integration tests against a real
database (overlap guard, concurrent assignment, concurrent status change, tenant isolation,
revoked sessions, disabled technician, audit of failed logins, Smart Assign).

Also run on the host: `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check .`
(all passed).

## Health endpoints (against the running stack)
- `GET /api/v1/health/live` -> `200 {"status":"ok"}`
- `GET /api/v1/health/ready` -> `200 {"status":"ok","database":"up"}`
- With the `db` container stopped: `ready` -> `503 {"status":"unavailable","database":"down"}`,
  `live` stays `200`. After restarting `db`, `ready` returned `200` again without restarting the API.

## Web (Bun, Next.js 16)
```bash
cd web && bun run lint && bun run typecheck && bun run test:ci && bun run build
```
Result: all four exit 0; 16 tests pass (translation parity EN/RU, time-zone conversion, API helpers).

## By hand in the browser
- Sign-in with a seeded dispatcher who belongs to two organizations; organization picker shown.
- Dashboard figures and charts come from `GET /reports/summary`.
- Request #16: *Mark as triaged* changed the status and appended a history entry.
- Request #28 (triaged): Smart Assign proposed two HVAC technicians, "Best match" applied in one click,
  status became *Scheduled*; the booking showed in the week and day schedule at the right position.
- A state-changing request without the CSRF header was refused with `403`.

## Known gaps in verification
- The host (Windows with Smart App Control) cannot import `pydantic_core`, so tests that import the
  app run in Docker. Cause and details: see `KNOWN_LIMITATIONS.md`.
- No web component/E2E browser tests yet; no tests for the Android app (not built yet).
