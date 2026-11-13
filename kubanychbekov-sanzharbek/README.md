# FixFlow

> Demo video: TODO (YouTube link goes here before submission)

Field-service management platform: **FastAPI + PostgreSQL** backend, **Next.js** web app (customers,
dispatchers, administrators) and a **Flutter** Android app for technicians. All three share one
database. Honest status of every requirement: [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md).

## Status

Working end to end (verified, see [docs/VERIFICATION.md](docs/VERIFICATION.md)): sign-in with server sessions and
login lockout, organizations and roles, requests with the full lifecycle, technician scheduling with a
database-level overlap guard, **Smart Assign** (the original feature, [docs/PRODUCT_DECISIONS.md](docs/PRODUCT_DECISIONS.md)),
notes, photos, estimates with approval, inventory with atomic write-off, SLA with working hours, preventive
maintenance, notifications, customer feedback, audit log, EN/RU web UI, and an Android app with an offline queue.
Also working: staff and roles, service-category administration, technician skills and availability, SLA report, and
live updates (server-sent events, the lists refresh without a reload). **Not done / limited:** the Android app does
not listen to the live stream (it refreshes on start, pull-to-refresh and sync), the APK is not yet confirmed on a real
phone, no browser end-to-end tests. Full, honest list: [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md).

## Requirements and verified versions

| Tool | Version used |
|---|---|
| Docker Desktop (Compose v2) | 29.x |
| `uv` | 0.11+ (Python 3.13 is provided by the backend image) |
| Bun | 1.4 |
| Flutter / Dart | 3.50 / 3.14 |
| JDK for the Android build | 17 |
| Android SDK | platform 36, build-tools 36.0.0 |

## Run the backend and database

```bash
cp .env.example .env            # demo-only values
docker compose up --build -d    # PostgreSQL + API + web, migrations run automatically
docker compose run --rm backend python -m app.seed         # demo data (safe to repeat)
docker compose run --rm backend python -m app.seed_extra   # plans, estimates, SLA and conflict cases (safe to repeat)
./scripts/smoke.sh              # real HTTP lifecycle, a 409 double booking, tenant isolation
```

- Web: http://localhost:3000 (the `web` service; the section below is for development without Docker)
- API: http://localhost:8000 (OpenAPI at `/docs`), health: `/api/v1/health/live` and `/ready`
- Ports can be changed with `API_PORT` in `.env`.
- Reset the local demo environment (**destroys the local database and uploads**):
  `docker compose down -v`
- Migrations only: `docker compose run --rm backend alembic upgrade head`
- Reset only affects the local Docker volumes; it never touches an external database (`DATABASE_URL` is not read by it).
- Demo accounts, IDs and the shared password `Demo-2345!` are fixed and for the demo only; repeating the seed adds nothing.

### Dev checks without external services (SEED-06)
- **Offline Android:** switch the phone to airplane mode, or `docker compose stop backend`, add notes/photos in the app,
  then turn the connection back on: the queue sends each item once. `mobile/test/live` (run with `FIXFLOW_API=http://localhost:8000`)
  automates it, including a lost response after the server already processed the request.
- **Concurrent requests:** `cd backend && pytest tests/test_scheduling_api.py tests/test_inventory_api.py tests/test_sla_api.py`
  fire parallel requests at PostgreSQL (double booking, last stock units, one SLA escalation); `./scripts/smoke.sh` shows one 409.
- **Whole scenario:** `python scripts/e2e_scenario.py http://localhost:8000`.

## Run the web app

```bash
cd web
bun install --frozen-lockfile
bun run dev                     # http://localhost:3000
```
It talks to the API through its own `/bff` proxy (set `API_URL` if the API is not on
`http://localhost:8000`). Sign in with a demo account below.

Web screens by role (EN/RU switch in the top bar):

| Screen | Path | Who |
|---|---|---|
| Dashboard, requests, request detail (history, estimates, photos, feedback) | `/app`, `/app/requests` | all (technicians see only their work on mobile) |
| New request | `/app/requests/new` | customer |
| Schedule and assignment (Smart Assign) | `/app/schedule` | dispatcher, admin |
| SLA queue (on track / at risk / overdue) | `/app/overdue` | dispatcher, admin |
| Inventory with low stock, maintenance plans, technicians | `/app/inventory`, `/app/maintenance`, `/app/technicians` | dispatcher, admin (admin edits) |
| Working hours and holidays, audit log | `/app/settings`, `/app/audit` | admin |
| Notifications | `/app/notifications` | all |

## Demo accounts (seeded, one shared **demo-only** password: `Demo-2345!`)

| Role | Organization A ("AIT Facility") | Organization B ("Nord Service") |
|---|---|---|
| Administrator | `admin.a@fixflow.test` | `admin.b@fixflow.test` |
| Dispatcher | `dispatcher.a@fixflow.test` | `dispatcher.b@fixflow.test` |
| Customer | `customer1.a@fixflow.test` ... `customer3.a@...` | `customer1.b@...`, `customer2.b@...` |
| Technician | `tech1.a@...` ... `tech4.a@...` | `tech1.b@...`, `tech2.b@...` |

`dispatcher.a@fixflow.test` is also a **customer** in organization B (one user, two organizations,
different roles).

## Android app (technician)

```bash
cd mobile
flutter pub get
flutter build apk --debug       # -> mobile/build/app/outputs/flutter-apk/app-debug.apk
```

Connecting to the local API (no secrets are stored in the APK; the server address is typed at sign-in):

- **Android emulator:** `http://10.0.2.2:8000` (the emulator's alias for the computer's localhost; the default).
- **Physical phone on the same Wi-Fi:** `http://<computer IP>:8000` (allow port 8000 in the firewall).
- The debug/release manifest allows plain HTTP for local testing; use HTTPS in production.

State management: **provider + ChangeNotifier** (`lib/state/app_state.dart`). Local persistent
storage: **sembast** (a file-based document database): session, last synchronized tasks and the
offline queue. Sign in as a technician demo account.

## Checks

```bash
# backend (inside Docker, real PostgreSQL)
docker compose --profile test run --rm backend-tests
# web
(cd web && bun install --frozen-lockfile && bun run lint && bun run typecheck && bun run test:ci && bun run build)
# mobile
(cd mobile && flutter pub get && dart format --output=none --set-exit-if-changed lib test && flutter analyze && flutter test)
```
All of the above in one go: `./scripts/verify-all.sh` (on a machine where native Python wheels are blocked, run it as
`BACKEND_TESTS_IN_DOCKER=1 ./scripts/verify-all.sh`: static checks on the host, tests in Docker).
What was actually run and its results: [docs/VERIFICATION.md](docs/VERIFICATION.md).

## Documentation
[Architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) · [Product decisions](docs/PRODUCT_DECISIONS.md) ·
[Known limitations](docs/KNOWN_LIMITATIONS.md) · [Verification](docs/VERIFICATION.md) · [AI usage](docs/AI_USAGE.md) ·
[Video script](docs/VIDEO_SCRIPT.md) · [Submission checklist](docs/SUBMISSION_CHECKLIST.md) · [Who owns what](docs/WORKSTREAMS.md)
