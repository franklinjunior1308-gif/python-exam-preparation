# Known limitations

Status of work in progress. Nothing is marked done unless it works end to end.

## Working now (verified by hand against the running stack)
- Docker Compose: PostgreSQL + backend with health checks and Alembic migration on start.
- Login/logout with server-side sessions, `GET /me`, organization selection, tenant-scoped requests.
- Request lifecycle state machine (97 unit tests), conditional-UPDATE transitions, status history, audit rows.
- Request list (server pagination, search, filters, sorting), create, detail with allowed actions.
- Dashboard numbers and charts computed from the database; English and Russian UI.
- Seed command (`python -m app.seed`): 2 organizations, demo users in every role, 54 requests.

## Also working now
- Scheduling: skills, weekly availability, absences, assign / reschedule / unassign / decline,
  PostgreSQL exclusion constraint against overlapping bookings, idempotent replay of the same assignment,
  schedule view (day and week) and **Smart Assign** (see `PRODUCT_DECISIONS.md`).
- 140 backend tests on PostgreSQL in Docker, 16 web tests.

## Not implemented yet (do not treat as done)
- **Android app (Flutter)**: not started. No offline queue, no APK.
- **Web**: no estimates UI, no inventory/admin screens, no notifications UI, no live updates
  (WebSocket/SSE), no photo upload on requests, no admin editing of technician skills/availability
  (they exist in the database and seed, but only via seed/SQL for now).
- **Backend modules**: estimates and versions (EST-*), inventory and idempotent material usage (INV-*),
  SLA clock and escalation (SLA-*), preventive maintenance (PM-*), notes/attachments and files
  (COMM-*), notifications, rate limiting on login, idempotency keys for notes/materials (API-03/04),
  request-ID structured logging, completion with note + photo (LIFE-05), WebSocket/SSE updates (API-06).
- **Not covered by tests yet**: web browser/E2E tests, concurrency for estimates/inventory (modules
  missing), file protection tests, report correctness tests, multi-worker (SEC-07) tests.
- Customers see every active property of their organization (there is no customer-to-property link yet).
- `scripts/smoke.sh` only checks readiness; `scripts/verify-all.sh` fails until the mobile app exists.
- `compose.yaml` has no `web` service yet; the web app is run with `bun run dev`.
- Seed has no inventory, plans or technician assignments, so those requirements' seed data is missing.

## Environment notes
- On the author's Windows machine Smart App Control blocks some unsigned native Python wheels
  (e.g. `pydantic_core`), so the backend is run and tested inside Docker; pure-logic tests run on the host.
