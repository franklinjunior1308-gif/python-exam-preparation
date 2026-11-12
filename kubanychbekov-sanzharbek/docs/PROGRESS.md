# PROGRESS (read this first after a context reset)

Last updated: 2026-11-13 ~00:15 (Asia/Bishkek). Deadline: **Sunday 2026-11-15 18:00**; access to the shared
GitHub repository opens **Sunday 16:00**. **Nothing has been pushed to GitHub and nothing may be pushed
before then** (see "Submission" at the end).

## Where things live
- Work repo (local git only, no remote): `C:\Users\ASUS ROG STRIX\fixflow\` (git root). The project is the folder
  `kubanychbekov-sanzharbek/` (this folder goes into the shared repo; it has no nested `.git`).
- Toolchain outside the repo: Flutter `C:\dev\flutter`, JDK 17 `C:\dev\jdk17`, Android SDK `C:\dev\android`,
  downloads `C:\dev\installers`, short temp dir `C:\dev\tmp`, Bun (winget), Docker Desktop, `uv` via `pip`.
- Demo password for every seeded account: `Demo-2345!` (demo-only). Accounts: see `README.md`.
- Docker volumes `kubanychbekov-sanzharbek_db_data` and `_uploads` hold the demo data: **never run `docker compose down -v`**.

## Implemented features -> requirements (PDF `FixFlow_Requirements_RU.pdf`)

| Area | Implemented | Requirement ids |
|---|---|---|
| Stack & run | FastAPI/SQLAlchemy 2/Alembic/PostgreSQL, uv lockfile, Compose `db`+`backend` with healthchecks, migrations on start, seed command | TECH-01,04,05,06,07 |
| Health | `GET /health/live`, `/ready` (503 when DB is down) | API-08, TECH-07 |
| Auth | Argon2, server-side sessions + JWT carrying a session id, expiry/revocation, disabled users, `GET /me`, failed-login audit (no password logged) | AUTH-01,02,04,05, ROLE-05 |
| Orgs & roles | explicit `X-Organization-Id` verified every request, membership per org, one user in two orgs (seed), 4 roles | ROLE-01..04, AUTH-03, PROD-03 |
| Isolation | all queries scoped by org; 404 for other orgs/customers; composite FKs `(organization_id,id)` | SEC-01, DATA-02,05 |
| Requests | create (title 5-120, description 20-3000: server + DB CHECK), list with server pagination/search/filters/sort/SLA filter, detail with allowed actions, history, priority/category change with reason | REQ-01 (no photos in web form yet),02,03,04,05,06 |
| Lifecycle | full state machine, compare-and-set transitions, atomic history + audit | LIFE-01..04,06..09 |
| Completion | final note >= 20 chars + >= 1 photo, idempotent | LIFE-05 (materials check missing) |
| Scheduling | skills, weekly availability, absences, min 30 min, no past, half-open overlap, **PostgreSQL exclusion constraint**, 409 for the loser, candidates with reasons, assign/reschedule/unassign/decline, day+week view | SCHED-01..07, DATA-03 |
| Original feature | **Smart Assign** (earliest free slot per qualified technician), documented in `PRODUCT_DECISIONS.md` | WEB-09, DOC-03 |
| Estimates | versions, immutable after submit, customer approve/reject (reason), parallel decisions -> one wins, work-start gate until approved, whole-tyiyn half-up rounding | EST-01..06, DATA-04 |
| Inventory | items, replenishment log, non-negative stock (CHECK), atomic idempotent write-off with price snapshot, last-units race safe, low stock + notification | INV-01..06 |
| SLA | working hours/holidays settings (admin), SLA in working time per request (budget by priority; estimate waits pause the clock; result fixed at completion), ON_TRACK/AT_RISK/OVERDUE, overdue queue, one-time escalation (DB unique) via `python -m app.sla_scan` | SLA-01..07, ORG-02 |
| Preventive maintenance | WEEKLY/MONTHLY plans per active asset, generation up to a date with DB unique (plan,date), parallel-safe, disable + retired-asset stop, history per plan, asset summary, local command `python -m app.pm_generate` | PM-01..05, ASSET-04,05 |
| Notes/files | immutable notes (public/internal), photo validation by decoding (JPEG/PNG/WebP, 10 MiB, pixel caps), server-side file names, authorized download only | COMM-01,02,05,06, SEC-04 |
| Notifications | stored per recipient+org: assignment created/changed/removed/declined, completion, estimate submitted/decision, low stock, SLA overdue, maintenance due | COMM-03,04 |
| Idempotency | `client_command_id` unique per org for notes, photos, completion, materials; same id + other payload = 409 | API-03,04, MOB-06 |
| Reports | dashboard summary computed from the DB in the org timezone | REPORT-01,02 (partly),05 |
| Web | landing (dark tech), sign-in, org picker, dashboard + charts, requests list/new/detail, assignment panel, schedule day/week, EN/RU, BFF proxy with httpOnly cookie + CSRF header, responsive, keyboard focus | WEB-01..08 (partly), DOC-07 |
| Android | sign-in, org choice, task list from local DB (offline), details, accept/decline/start/block/resume/complete, notes + photos with offline queue, retry/delete, conflicts kept until the user decides, 401 keeps the queue, notifications, profile, EN/RU | MOB-01..08 (partly) |
| Docs | README, ARCHITECTURE, API, PRODUCT_DECISIONS, KNOWN_LIMITATIONS, VERIFICATION, this file | DOC-01..05 |

### Verified vs. implemented
- **Implemented AND verified by automated tests**: lifecycle, scheduling/overlap/concurrency, Smart Assign, estimates,
  inventory, notes/photos/completion, notifications, SLA, maintenance, tenant isolation, idempotency, health
  (live+ready incl. DB down, also checked by hand), offline queue/sync logic and key Android screens.
- **Implemented, verified only by hand in the browser**: web landing, sign-in, dashboard/charts, request list/detail,
  assignment panel, schedule day/week, EN/RU toggle (no web E2E tests).
- **Not verified yet**: the Android app on a device/emulator (no APK yet), multi-worker runs (SEC-07), accessibility
  audit beyond keyboard focus/labels.

## Test results (last full runs)
- **Backend**: `docker compose --profile test run --rm backend-tests` -> **225 passed, 0 failed** (ruff + ty clean).
  Pure tests: lifecycle 97, scheduling 19, money 3, SLA 9, maintenance dates 7. The rest are integration tests on
  real PostgreSQL (overlap guard, concurrency, isolation, notes/photos/completion, estimates, inventory, SLA,
  maintenance, estimates/inventory races).
- **Web**: `bun run lint && bun run typecheck && bun run test:ci && bun run build` -> all exit 0; **23 tests**
  (EN/RU key parity, timezone conversion, API helpers, money/estimate totals).
- **Mobile**: `flutter analyze` -> No issues; `flutter test` -> **22 passed** (10 offline queue/sync + 12 app/widget/i18n).
- Health verified live: `live` 200, `ready` 200, `ready` 503 with the DB stopped, recovers without restarting the API.

## Known errors / caveats
- Windows **Smart App Control blocks `_pydantic_core.pyd`** on the host (error 4551): any backend test importing the
  app fails on the host; run backend tests in Docker. Only pure tests run on the host.
- Flutter widget tests that touch sembast must run inside `tester.runAsync` (fake-async otherwise hangs); run
  `flutter test --timeout=60s`. Detail screens are long: use a tall test surface.
- Web has no inventory/plan/admin/notification screens yet; Android has no materials screen. Extra seed DONE
  (`python -m app.seed_extra`, insert-only, marker audit event). Full list: `KNOWN_LIMITATIONS.md`.
- The dev database was reset twice early on; do not reset it again.
- Several shell snippets with Windows backslashes break inside Python heredocs: use the Write tool for files.

## Android SDK / APK state (2026-11-13 ~00:15)
- Installed: Flutter 3.50.0 (Dart 3.14) `C:\dev\flutter`, JDK 17 `C:\dev\jdk17`, Android SDK `C:\dev\android`
  (cmdline-tools, platform-tools, platforms;android-36, build-tools;36.0.0; NDK 28.2.13676358 is being downloaded by
  Gradle). Licenses were accepted by the user. `flutter config` points at these paths.
- Gradle 9.5.0 is in `~/.gradle/wrapper/dists/gradle-9.5.0-all/aca6g93cdtcf0oapcfka748qh/gradle-9.5.0` (extracted
  with `tar`, marker `gradle-9.5.0-all.zip.ok` present).
- **APK BUILT (2026-11-13 00:00)**: `mobile/build/app/outputs/flutter-apk/app-debug.apk`, 154.7 MB, SHA-256
  `AE569397F5A56CCD6175133B909C5E8462CFBD7C264EDFAC56D276B454B9C5BC`; package `kg.fixflow.fixflow_tech`,
  minSdk 24 / targetSdk 36, INTERNET permission, ABIs arm64-v8a/armeabi-v7a/x86_64 (`aapt2 dump badging`).
  The Gradle build took ~25 min (NDK r28c, Platform 35, CMake installed automatically). The APK is git-ignored.
  Not yet installed on a phone/emulator (no emulator image on this PC).
- **Live integration test passes**: `FIXFLOW_API=http://localhost:8000 flutter test test/live` runs the real app
  code against FastAPI + PostgreSQL (sign-in, tasks, offline note with a lost response -> exactly one note on the
  server, photo multipart upload, authorized download, 401 without a session, refused state change).

### Gradle / APK problems met so far (and fixes)
1. Gradle wrapper download of `gradle-9.5.0-all.zip` stalled at 0 MB (no stall detection) -> downloaded with a
   `curl.exe -L -C -` resume loop into `C:\dev\installers` and placed into the wrapper cache.
2. `Expand-Archive` of that zip silently rolled back ("distribution does not contain any directories") -> use
   `tar -xf <zip> -C <dist dir>`, then create `gradle-9.5.0-all.zip.ok`.
3. `java.io.IOException: Unable to establish loopback connection`: the JDK `Pipe.open()` creates a Unix-domain
   socket file in `%TEMP%` and the path has spaces. `netsh winsock reset` + reboot did NOT fix it. Fix: set
   `JAVA_TOOL_OPTIONS=-Djdk.net.unixdomain.tmpdir=C:\dev\tmp -Djava.net.preferIPv4Stack=true` (create the dir).
4. Gradle stalls on dependency downloads with many open connections (cache stops growing for minutes) -> kill
   `java` and start the build again; caches are kept. Idle network speed is ~1.5 MB/s.
5. `sdkmanager` package installs hung with no progress -> downloaded the three zips with `curl -C -` and unpacked
   them into `C:\dev\android\{platform-tools, platforms\android-36, build-tools\36.0.0}`.
6. Last resort: build in a Linux container (Flutter + JDK 17 + Android SDK image, mount `mobile/`).

## Remaining mandatory work, in priority order (SLA and preventive maintenance backends are DONE)
1. ~~APK~~ DONE (see "Android SDK / APK state"); rebuild after Android changes with the recipe below.
2. ~~Seed completion~~ DONE (commit f5da98e): 3 plans/org (one generated), estimates approved/awaiting/rejected+v2,
   at-risk SLA request, conflict candidate. Verified through the API (6 AT_RISK, 14 OVERDUE).
3. **Web screens** (all backend APIs exist; SLA badge/filter/overdue queue and estimates UI are DONE): inventory + low stock; maintenance plans + asset page (next/last service); admin screens
   (working hours, holidays, categories/skills, staff/roles, technician availability); notifications inbox;
   customer feedback; photo upload in the request form; audit feed; SLA report.
4. **Android**: materials screen (`POST /requests/{id}/materials`, online only), estimate total on the task.
5. **Backend gaps**: customer feedback endpoint (COMM-07/WEB-02), audit feed endpoint (ORG-05), technician
   availability/skills edit API (ORG-01), user/role management + role-change audit (ORG-04, AUTH-05), login rate
   limit (SEC-03), request-ID structured logging (SEC-08), live updates SSE/WebSocket (API-06).
6. **Scripts/docs**: `scripts/smoke.sh` (real lifecycle + a 409), `scripts/verify-all.sh`, `web` service in
   `compose.yaml`, `docs/AI_USAGE.md` (missing), update `VERIFICATION.md`, record the 5-minute video.
7. **Submission** only on Sunday after 16:00 (see below).

## Commands to continue / verify
```bash
# from the project folder (git-bash or PowerShell)
cd "C:/Users/ASUS ROG STRIX/fixflow/kubanychbekov-sanzharbek"

# Docker Desktop must be running. Start / rebuild backend + DB (data volumes are kept):
docker compose up -d --build backend
docker compose run --rm backend python -m app.seed_extra       # plans/estimates/SLA demo data, idempotent
docker compose run --rm backend python -m app.seed             # skips organizations that already exist
docker compose run --rm backend python -m app.sla_scan         # escalate overdue requests (idempotent)
docker compose run --rm backend python -m app.pm_generate      # generate due maintenance requests (idempotent)
curl http://localhost:8000/api/v1/health/ready                  # {"status":"ok","database":"up"}

# Backend tests on PostgreSQL (the only place where app-importing tests can run on this PC):
docker compose --profile test run --rm backend-tests

# New migration after changing models (autogenerate, format, apply):
docker compose build backend
docker compose run --rm -v "$PWD/backend/alembic/versions:/app/alembic/versions" backend alembic revision --autogenerate -m "name"
(cd backend && python -m uv run ruff format . && python -m uv run ruff check . --fix)
docker compose up -d --build backend

# Host-side backend quality gates (no app import needed):
(cd backend && python -m uv run ruff check . && python -m uv run ty check . && python -m uv run python -m pytest tests/test_lifecycle.py tests/test_scheduling_rules.py tests/test_money.py tests/test_sla.py tests/test_maintenance_dates.py -q)

# Web (open a NEW PowerShell so Bun is on PATH; scripts use `bun --bun`):
(cd web && bun run lint && bun run typecheck && bun run test:ci && bun run build)
(cd web && bun run dev)                                         # http://localhost:3000 (API at :8000)

# Mobile analyze + tests (PowerShell, env in the same window):
#   $env:JAVA_HOME="C:\dev\jdk17"; $env:Path="C:\dev\flutter\bin;C:\dev\jdk17\bin;"+$env:Path
(cd mobile && flutter analyze && flutter test --timeout=60s)
```

### Build the APK (PowerShell, ONE window; run in the background and watch the log)
```powershell
New-Item -ItemType Directory -Force C:\dev\tmp | Out-Null
$env:JAVA_TOOL_OPTIONS = "-Djdk.net.unixdomain.tmpdir=C:\dev\tmp -Djava.net.preferIPv4Stack=true"
$env:JAVA_HOME="C:\dev\jdk17"; $env:ANDROID_HOME="C:\dev\android"; $env:ANDROID_SDK_ROOT="C:\dev\android"
$env:Path="C:\dev\flutter\bin;C:\dev\jdk17\bin;C:\dev\android\platform-tools;"+$env:Path
cd "C:\Users\ASUS ROG STRIX\fixflow\kubanychbekov-sanzharbek\mobile"
flutter build apk --debug *> "$env:TEMP\apk-build.txt"      # slow the first time (NDK + Maven downloads)
Get-Content "$env:TEMP\apk-build.txt" -Tail 20
```
If the log or `~/.gradle/caches` stops growing for more than 5 minutes: `Get-Process java | Stop-Process -Force` and
run it again. If the Gradle distribution is missing: download `gradle-9.5.0-all.zip` with `curl.exe -L -C -`, copy it
to `~/.gradle/wrapper/dists/gradle-9.5.0-all/aca6g93cdtcf0oapcfka748qh/`, `tar -xf` it there, create
`gradle-9.5.0-all.zip.ok`.

## CURRENT NEXT STEP (resume here)
1. TWO SESSIONS WORK IN PARALLEL (fork 1 and fork 2, same repo): fork 2 owns `web/` and the extra seed; fork 1 owns
   `mobile/`, `docs/VERIFICATION.md` and the backend gaps (feedback, audit feed, login rate limit, request-ID logs,
   live updates). Never `git add -A`; commit only your own paths.
2. DONE 2026-11-13 (fork 1): Android materials screen (`mobile/lib/ui/materials_screen.dart`, online-only write-off with
   stable command id, insufficient-stock error mapped en/ru) + approved estimate total on the task details; 28 Flutter
   tests pass, `flutter analyze` clean; APK rebuild started. Fork 1 next: backend gaps (feedback, audit feed, login rate
   limit, request-ID logs, live updates, LIFE-05), then `scripts/smoke.sh`, `docs/AI_USAGE.md`.
3. After each module: `ruff`/`ty`, tests in Docker, commit locally, keep this file current.

## Submission (do not do early)
Only on Sunday 2026-11-15 after 16:00: accept the invitation, create branch `submission/kubanychbekov-sanzharbek`,
copy the folder `kubanychbekov-sanzharbek/` (without `.git`, `node_modules`, `.next`, `build`, `.dart_tool`, `.env`)
into the shared repo, commit, push, open the PR titled `FixFlow: Kubanychbekov Sanzharbek`, **do not merge**. Put the
YouTube link at the top of `README.md`. The root files of the shared repo belong to the organizers: do not change them.
