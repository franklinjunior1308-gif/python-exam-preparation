# PROGRESS (read this first after a context reset)

Last updated: 2026-11-12 ~22:50 (Asia/Bishkek). Deadline: **Sunday 2026-11-15 18:00**; shared GitHub
repository access opens **Sunday 16:00**. **Nothing has been pushed to GitHub, and nothing may be
pushed before then** (see "Submission" below).

## Where things live
- Work repo (local git only): `C:\Users\ASUS ROG STRIX\fixflow\` (git root). The project is the folder
  `kubanychbekov-sanzharbek/` (this is the folder that goes into the shared repo; no nested `.git`).
- Toolchain (outside the repo): Flutter `C:\dev\flutter`, JDK 17 `C:\dev\jdk17`, Android SDK
  `C:\dev\android`, installers/zips `C:\dev\installers`, Bun (winget), Docker Desktop, `uv` via `pip`.
- Demo password for every seeded account: `Demo-2345!` (demo-only). Accounts: see `README.md`.

## Implemented features -> requirements (PDF `FixFlow_Requirements_RU.pdf`)

| Area | Implemented | Requirement ids |
|---|---|---|
| Stack & run | FastAPI/SQLAlchemy 2/Alembic/PostgreSQL, uv lockfile, Docker Compose `db`+`backend` with healthchecks, migrations on start, seed command | TECH-01,04,05,06,07 |
| Health | `GET /health/live`, `/ready` (503 when DB is down) | API-08, TECH-07 |
| Auth | Argon2, server-side sessions + JWT with session id, expiry/revocation, disabled users, `GET /me`, failed-login audit (no password logged) | AUTH-01,02,04,05, ROLE-05 |
| Orgs & roles | explicit `X-Organization-Id` verified every request, membership per org, one user in two orgs (seed), 4 roles | ROLE-01..04, AUTH-03, PROD-03 |
| Isolation | all queries scoped by org; 404 for other orgs/customers; composite FKs `(organization_id,id)` | SEC-01, DATA-02,05 |
| Requests | create (title 5-120, description 20-3000 on server + DB CHECK), list with server pagination/search/filters/sort, detail with allowed actions, history | REQ-01(partly: no photos in web form),02,04,05,06 |
| Lifecycle | full state machine (97 unit tests), compare-and-set transitions, atomic history+audit | LIFE-01..04,06..09 |
| Completion | final note >= 20 chars + >= 1 photo, idempotent | LIFE-05 (materials check missing) |
| Scheduling | skills, weekly availability, absences, min 30 min, no past, half-open overlap, **PostgreSQL exclusion constraint**, 409 for the loser, candidates with reasons, assign/reschedule/unassign/decline, day+week view | SCHED-01..07, DATA-03 |
| Original feature | **Smart Assign** (earliest free slot per qualified technician) | WEB-09 (docs: `PRODUCT_DECISIONS.md`) |
| Estimates | versions, immutable after submit, customer approve/reject(reason), parallel decisions -> one wins, start gate until approved, whole-tyiyn rounding | EST-01..06, DATA-04 |
| Inventory | items, replenishment log, non-negative stock (CHECK), atomic idempotent write-off with price snapshot, last-units race safe, low stock + notification | INV-01..06 |
| Notes/files | immutable notes (public/internal), photo validation by decoding (JPEG/PNG/WebP, 10 MiB, pixel caps), server-side file names, authorized download only | COMM-01,02,05,06, SEC-04 |
| Notifications | stored per recipient+org: assignment created/changed/removed/declined, completion, estimate submitted/decision, low stock | COMM-03,04 (partly) |
| Idempotency | `client_command_id` unique per org for notes, photos, completion, materials; same id+other payload = 409 | API-03,04, MOB-06 |
| Reports | dashboard summary computed from DB in org timezone | REPORT-01,02(partly),05 |
| Web | landing (dark tech), sign-in, org picker, dashboard + charts, requests list/new/detail, assignment panel, schedule, EN/RU, BFF proxy with httpOnly cookie + CSRF header, responsive, keyboard focus | WEB-01..08 (partly), DOC-07 |
| Android | sign-in, org choice, task list (local DB, offline), task details, accept/decline/start/block/resume/complete, notes + photos with offline queue, retry/delete, conflicts kept until user decides, 401 keeps queue, notifications, profile, EN/RU | MOB-01..08 (partly) |
| Docs | README, ARCHITECTURE, API, PRODUCT_DECISIONS, KNOWN_LIMITATIONS, VERIFICATION, this file | DOC-01..05 |

## Test results (last full runs)
- **Backend**: `docker compose --profile test run --rm backend-tests` -> **187 passed, 0 failed**
  (ruff clean, ty clean). 97 lifecycle, 19 scheduling rules, 3 money, 2 health, 66 integration tests on
  real PostgreSQL (overlap guard, concurrency, isolation, notes/photos/completion, estimates, inventory).
- **Web**: `bun run lint && bun run typecheck && bun run test:ci && bun run build` -> all exit 0, 16 tests.
- **Mobile**: `flutter analyze` -> No issues; `flutter test` -> **22 passed** (10 offline-queue/sync,
  12 app/widget/i18n).
- Health verified live: `live` 200, `ready` 200, 503 with DB stopped, recovers without API restart.

## Known errors / caveats
- Windows **Smart App Control blocks `_pydantic_core.pyd`** on the host (error 4551), so any backend test
  that imports the app fails on the host; run backend tests in Docker. Host can run only pure tests.
- `widget tests` that touch sembast must run inside `tester.runAsync` (fake-async hangs otherwise).
- `flutter test` can hang if a test misuses fake async: run with `--timeout=60s`.
- Seed data has no estimate/SLA/plan cases yet; web has no estimate/inventory screens; Android has no
  materials screen. Full list: `KNOWN_LIMITATIONS.md`.
- The dev database was reset twice earlier (before this note); do **not** reset it again unless needed.

## Android SDK / APK state
- Flutter 3.50.0 (Dart 3.14), JDK 17, Android SDK (platform-tools, platforms;android-36,
  build-tools;36.0.0) installed manually; licenses accepted by the user; `flutter config` points at them.
- **APK not built yet.** `flutter build apk --debug` reaches "Running Gradle task 'assembleDebug'" and then
  stalls because Gradle's wrapper cannot finish downloading `gradle-9.5.0-all.zip` (slow connection, no
  stall detection). A manual resumable download is running into `C:\dev\installers\gradle-9.5.0-all.zip`
  (240 MB; ~70 MB done at 22:47).
- After the zip is complete, install it into Gradle's cache, then build (commands below).
  Expected APK: `mobile/build/app/outputs/flutter-apk/app-debug.apk`.

## Remaining mandatory work, in priority order
1. **Finish the APK** (install Gradle zip, `flutter build apk --debug`, record size/path, optionally run on an
   emulator/phone). Add `flutter build apk` result to `VERIFICATION.md`.
2. **SLA** (SLA-01..07): working hours + holidays settings, budget by priority, pause during
   AWAITING_APPROVAL, ON_TRACK/AT_RISK/OVERDUE, one-time escalation notification, local command to scan.
3. **Preventive maintenance** (PM-01..05): plans (WEEKLY/MONTHLY), generate requests with unique
   (plan, date), concurrent-safe, command + web display.
4. **Seed completion** (SEED-01..05): estimates, plan, SLA cases, inventory exists; reset command documented.
5. **Android**: materials screen (API exists), estimate info on task, MOB-09 docs check, MOB-10 build.
6. **Web screens**: estimates (create/submit/decide), inventory/admin, notifications, SLA/overdue queue,
   customer feedback, photo upload in request form, admin editing of skills/availability/categories/holidays
   (ORG-*, ASSET-*), audit feed.
7. **Live updates** (API-06, SSE/WebSocket) and request-ID structured logging (SEC-08), login rate limit (SEC-03).
8. **Scripts**: `scripts/verify-all.sh` (needs web+mobile real), `scripts/smoke.sh` (real lifecycle + 409),
   add `web` service to `compose.yaml` (port 3000, depends_on backend).
9. **Docs**: `AI_USAGE.md` (missing), update `VERIFICATION.md`, record the demo video (README-03/04/05).
10. **Submission** (see below) — leave the full window 16:00-18:00 on Sunday.

## Commands to continue / verify
```bash
# Everything from the project folder:
cd "C:/Users/ASUS ROG STRIX/fixflow/kubanychbekov-sanzharbek"

# Backend + DB (Docker Desktop must be running). DO NOT run `down -v` (it wipes demo data).
docker compose up -d --build backend
docker compose run --rm backend python -m app.seed          # skips orgs that already exist
docker compose --profile test run --rm backend-tests        # full backend suite on PostgreSQL

# New migration after changing models (autogenerate, then format and apply):
docker compose build backend
docker compose run --rm -v "$PWD/backend/alembic/versions:/app/alembic/versions" backend alembic revision --autogenerate -m "name"
(cd backend && python -m uv run ruff format . && python -m uv run ruff check . --fix)
docker compose up -d --build backend

# Host-side quality gates for backend (no app import needed):
(cd backend && python -m uv run ruff check . && python -m uv run ty check . && python -m uv run python -m pytest tests/test_lifecycle.py tests/test_scheduling_rules.py tests/test_money.py -q)

# Web (Bun on PATH in a new PowerShell; run via `bun run`, scripts use `bun --bun`):
(cd web && bun run lint && bun run typecheck && bun run test:ci && bun run build)
(cd web && bun run dev)                                     # http://localhost:3000

# Mobile (PowerShell; env must be set in the same command):
#   $env:JAVA_HOME="C:\dev\jdk17"; $env:ANDROID_HOME="C:\dev\android"
#   $env:Path="C:\dev\flutter\bin;C:\dev\jdk17\bin;"+$env:Path
(cd mobile && flutter analyze && flutter test --timeout=60s)
```

### Finish the Gradle download and build the APK (PowerShell)
```powershell
# 1) wait until C:\dev\installers\gradle-9.5.0-all.zip is 240667887 bytes
(Get-Item C:\dev\installers\gradle-9.5.0-all.zip).Length
# resume if curl is no longer running:
curl.exe -L -C - --retry 80 --retry-delay 2 --retry-all-errors --speed-limit 20000 --speed-time 20 -o C:\dev\installers\gradle-9.5.0-all.zip https://services.gradle.org/distributions/gradle-9.5.0-all.zip
# 2) put it where the wrapper expects it (find the hash dir the wrapper created, or any 'dists\gradle-9.5.0-all\<hash>')
$d = "$env:USERPROFILE\.gradle\wrapper\dists\gradle-9.5.0-all\aca6g93cdtcf0oapcfka748qh"
New-Item -ItemType Directory -Force $d | Out-Null
Copy-Item C:\dev\installers\gradle-9.5.0-all.zip "$d\gradle-9.5.0-all.zip"
Expand-Archive "$d\gradle-9.5.0-all.zip" -DestinationPath $d -Force
New-Item "$d\gradle-9.5.0-all.zip.ok" -ItemType File -Force
# 3) build (slow first time: Gradle downloads Maven dependencies)
cd "C:\Users\ASUS ROG STRIX\fixflow\kubanychbekov-sanzharbek\mobile"
flutter build apk --debug
```
If Gradle still hangs on a dependency download, run the build in the background and watch the log;
the connection is slow (~0.5 MB/s) and some hosts stall - restart the build, caches are kept.

## CURRENT NEXT STEP
1. Finish the Gradle zip download (still running at last check), install it into Gradle's cache as above,
   run `flutter build apk --debug`, show the user the test results + APK path/size.
2. **SLA is partly done**: the pure working-time arithmetic exists in `backend/app/domain/sla.py` with 9
   unit tests (`tests/test_sla.py`, weekends/holidays/pauses/thresholds). Still to do for SLA-01..07:
   DB tables (org working-hours settings + holidays, per-request SLA events/pauses, escalation record),
   hook pauses to estimate AWAITING_APPROVAL start/end, expose state on requests + `/sla/overdue`,
   one-time escalation notification with a unique DB constraint, local command
   `python -m app.sla_scan`, tests (E2E-07: Friday evening HIGH request, holiday, estimate pause, one escalation).
3. Then preventive maintenance (PM-*).

## Submission (do not do early)
Only on Sunday 2026-11-15 after 16:00: accept the invitation, create branch
`submission/kubanychbekov-sanzharbek`, copy the folder `kubanychbekov-sanzharbek/` (without `.git`,
`node_modules`, `.next`, `build`, `.dart_tool`, `.env`) into the shared repo, commit, push, open the PR
titled `FixFlow: Kubanychbekov Sanzharbek`, **do not merge**. Put the YouTube link at the top of `README.md`.
