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
| APK | `flutter build apk --debug` | built `mobile/build/app/outputs/flutter-apk/app-debug.apk`, 190 285 451 bytes, SHA-256 `cc5b54e060f7d27f78f038686c5649f970aae1762b9a28e9cb52c67f86023dd8` (a build output; it is not committed) |

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

**Web screens added after the final run (2026-11-13, by hand in the browser against the running stack):** Staff and roles
(weak password rejected on the form; a member created and deactivated; removing the only administrator is refused with
the translated message), Categories (list with skills; a duplicate name gives the translated conflict), SLA report
(80 % on time, 10 finished, average 11 h 26 min over 30 days, per-priority table) and **live updates**: with the request
list open, two requests created through the API appeared in the same page without a reload (rows 0 -> 1 -> 2, indicator
"Live"); the stream answers `200 text/event-stream` through the web proxy. `bun run lint`, `typecheck`, `test:ci` (23)
pass. The Docker build of the web image and the full `verify-all.sh` were last run before these screens: rerun before
submission.

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

## Final full check - 2026-11-13
Run on the author's Windows machine, backend tests in Docker (`BACKEND_TESTS_IN_DOCKER=1`), HEAD `9b82d8e` plus docs.

| Part | Command | Result |
|---|---|---|
| Backend | `ruff check`, `ruff format --check`, `ty check`, `pytest` (PostgreSQL 17) | all clean, **269 passed** |
| Web | `bun run lint`, `typecheck`, `test:ci`, `build` | clean, 23 tests passed, production build succeeded |
| Android | `dart format`, `flutter analyze`, `flutter test`, `flutter build apk --debug` | clean, 28 passed (2 live tests skipped without `FIXFLOW_API`), APK built |

APK: `mobile/build/app/outputs/flutter-apk/app-debug.apk`, 190 285 451 bytes,
SHA-256 `cc5b54e060f7d27f78f038686c5649f970aae1762b9a28e9cb52c67f86023dd8`.
**Still not checked on a physical phone** (see `ANDROID_PHONE_TEST.md`).

**Do not run two backend-test runs against the same database at once.** The suite truncates shared tables, so two
parallel runs on `fixflow_test` deadlocked (`DeadlockDetected`, 16 failed and 50 errors in one attempt; a run alone
gives 269 passed). To run in parallel, give each run its own database:
`docker compose --profile test run --rm -e DATABASE_URL=postgresql+psycopg://fixflow:fixflow@db:5432/<name> -e TEST_DATABASE_URL=<same> backend-tests`
(the database is created on demand).


## Final full check after the last audit - 2026-11-13
`BACKEND_TESTS_IN_DOCKER=1 ./scripts/verify-all.sh` finished with `ALL CHECKS PASSED` (exit 0):

| Part | Result |
|---|---|
| Backend (`ruff check`, `ruff format --check`, `ty check`, `pytest` on PostgreSQL 17) | clean, **284 passed** |
| Web (`bun install --frozen-lockfile`, `lint`, `typecheck`, `test:ci`, `build`) | clean, **23 passed**, production build succeeded |
| Android (`dart format`, `flutter analyze`, `flutter test`, `flutter build apk --debug`) | clean, **37 passed** (2 live tests skipped inside verify-all), APK built |
| Live Flutter test against the real API (`FIXFLOW_API=http://localhost:8000 flutter test test/live`) | 2 passed |
| `./scripts/smoke.sh` on the running seeded stack | `smoke: all checks passed` (409 double booking, tenant isolation) |
| Clean-start rehearsal (separate compose project `rehearsal`, ports 18000/13000, own volumes) | build + readiness, seed and seed_extra, repeat adds nothing, `scripts/e2e_scenario.py` all checks passed, web `/` and `/login` answer 200, a container restart kept all 76 requests |

APK: `mobile/build/app/outputs/flutter-apk/app-debug.apk`, 190 285 451 bytes, SHA-256 `cc5b54e060f7d27f78f038686c5649f970aae1762b9a28e9cb52c67f86023dd8`.

Added in the last audit (each with automated tests): equipment and property management with history, reports with
period/category/technician filters, technician load, approved-estimate and material totals, request list technician and
date filters with due-date sorting, organization name/time zone, rework notification, session-revocation audit, request
body limit, SLA and earlier jobs on the technician's task, own availability, notes and one timeline in the web.

Not verified by an automated check: the full phone scenario (`docs/ANDROID_PHONE_TEST.md` steps 4-11) on a real device;
the candidate reported a successful sign-in and task list on a real phone. Browser end-to-end tests do not exist.
The rehearsal's two Docker volumes (`rehearsal_db_data`, `rehearsal_uploads`) were left in place on purpose.
