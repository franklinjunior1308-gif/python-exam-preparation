# Verification log

What was actually run, and what happened. Updated as work progresses. Sections below the first one are earlier
runs, kept for history; the numbers in the first section are the current ones.

## Final check, 2026-11-13 (Windows 11, Docker Desktop, PostgreSQL 17)

**`BACKEND_TESTS_IN_DOCKER=1 ./scripts/verify-all.sh` -> `ALL CHECKS PASSED`** (exit 0). It ran, in order:

| Step | Command | Result |
|---|---|---|
| Backend static | `uv sync --frozen`, `ruff check .`, `ruff format --check .`, `ty check .` | all clean (100 files formatted) |
| Backend tests | `docker compose --profile test run --rm backend-tests` (real PostgreSQL) | **245 passed**, 0 failed, 1 deprecation warning from a dependency |
| Web | `bun install --frozen-lockfile`, `lint`, `typecheck`, `test:ci`, `build` | all exit 0; **23 tests passed** |
| Mobile | `flutter pub get`, `dart format --output=none --set-exit-if-changed lib test`, `flutter analyze`, `flutter test` | clean; **28 passed** (2 live-backend tests are skipped without `FIXFLOW_API`) |
| APK | `flutter build apk --debug` | built `mobile/build/app/outputs/flutter-apk/app-debug.apk`, 190 268 742 bytes, SHA-256 `e0bd783215647002b4a6e7e5fddf3c81a1eaad5bb12f118b40bd95da04f42085` (a build output; it is not committed) |

Why the Docker switch: on the author's PC Windows Smart App Control blocks `pydantic_core`, so app-importing tests
cannot run on the host. Without the switch (`./scripts/verify-all.sh`) the same script runs `uv run pytest -q` on the
host, which is the form the organizers use.

**Clean start from nothing** (isolated Compose project with its own volumes and ports, so the working database was not
touched): `API_PORT=18000 WEB_PORT=13000 docker compose -p fixflowclean up -d --build` -> `db`, `backend`, `web` healthy;
migrations ran on start; `python -m app.seed` and `python -m app.seed_extra` filled the data; `GET /health/ready` ->
`{"status":"ok","database":"up"}`; the web login page returned 200; `API_URL=http://localhost:18000 py scripts/smoke.py`
-> `smoke: all checks passed` (lifecycle, double booking rejected with 409, other organization gets 404).

**Smoke test** on the working stack (`scripts/smoke.py`) also passed, including after the login lockout was added.

**By hand** (browser, built-in): inventory with two low-stock items, maintenance plans with last/next service,
notifications, admin working hours, technician skill edit (saved, lowercased by the server, then restored), photo upload
through the web proxy (270 bytes up, 270 bytes down), SLA totals 20 / 6 / 14, audit log, accessibility scan of 10 pages
(one unlabeled file input found and fixed), login lockout (5 failures, then 429 `too_many_attempts`).

**LAN check for the phone (2026-11-13):** `FIXFLOW_API=http://192.168.0.242:8000 flutter test test/live` -> 2 passed (the
app code reaches the API through the computer's Wi-Fi address); `GET http://192.168.0.242:8000/api/v1/health/ready` ->
200. Installing on a real phone and the 11-step scenario are described in `docs/ANDROID_PHONE_TEST.md`; their result
is recorded there only after they are run by hand.

**Whole scenario through the API** (`scripts/e2e_scenario.py`, 2026-11-13, against `http://10.116.90.235:8000`, the computer's address on the phone's hotspot): customer creates an HVAC request with a photo; dispatcher triages, Smart Assign lists suggestions, assigns `tech2.a`; a second booking of the same slot is refused with 409; the technician sees the task, accepts, starts; the note and the photo retried with the same command id are stored once; completion; the dispatcher sees COMPLETED with the final SLA and history SUBMITTED, TRIAGED, SCHEDULED, ACCEPTED, IN_PROGRESS, COMPLETED; the customer rates 5/5 and a second rating gets 409. Result: **all checks passed**. Finding: a completed visit frees its slot (a later booking of that time succeeds); the 409 check belongs before completion.

**Not verified:** the APK has not yet been installed on an emulator or a phone in this check (the live integration test
below exercised the same app code against the real API); no browser/E2E tests for the web; no multi-worker run
(SEC-07); the demo video is not recorded.

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
- (Early note, now outdated: the Android app has since been built and tested; see the final check above.)

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
