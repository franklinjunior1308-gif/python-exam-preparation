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

## Android (Flutter) - 2026-11-13
- `flutter analyze` -> **No issues found**; `flutter test` -> **22 passed** (10 offline-queue/sync, 12 app/widget/i18n).
- `flutter build apk --debug` -> **built** `mobile/build/app/outputs/flutter-apk/app-debug.apk`, 154.7 MB,
  SHA-256 `AE569397F5A56CCD6175133B909C5E8462CFBD7C264EDFAC56D276B454B9C5BC`. `aapt2 dump badging`: package
  `kg.fixflow.fixflow_tech`, versionName 0.1.0, minSdk 24, targetSdk 36, permission INTERNET, ABIs arm64-v8a,
  armeabi-v7a, x86_64. The first build took ~25 min on a slow connection (NDK, Platform 35, CMake, Maven artifacts).
  Not yet installed on a device or emulator.
- **Live integration test** (real app code -> real FastAPI -> real PostgreSQL), `test/live/live_backend_test.dart`:
  ```powershell
  $env:FIXFLOW_API="http://localhost:8000"; cd mobile; flutter test test/live --timeout=120s
  ```
  Result: **2 passed**. It signs in as `tech2.a@fixflow.test`, loads the real task list into the local database, queues
  an internal note, loses the server's first answer (phone "never heard back"), retries with the same command id and
  checks that exactly **one** note exists on the server, uploads a PNG photo from the queue (multipart), checks the
  local copy is removed, downloads the photo with the session (200) and without it (401), and checks that a
  forbidden state change is refused. A wrong password gives `invalid_credentials` and stores nothing. Without
  `FIXFLOW_API` the live tests are skipped, so the normal `flutter test` stays offline.
