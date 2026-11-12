# Known limitations

Status of work in progress. Nothing is marked done unless it works end to end.

## Working now (verified; see `VERIFICATION.md`)
- Docker Compose: PostgreSQL + backend with health checks and Alembic migrations on start.
- Auth: login/logout with server-side sessions, `GET /me`, organization selection, tenant isolation
  (server checks per request, composite foreign keys), failed-login audit.
- Requests: full lifecycle state machine, compare-and-set transitions, status history, audit rows,
  list with search/filters/sorting/pagination.
- Scheduling: skills, weekly availability, absences, assign / reschedule / unassign / decline, PostgreSQL
  exclusion constraint against overlapping bookings, idempotent assignment, day/week schedule view,
  **Smart Assign** (see `PRODUCT_DECISIONS.md`).
- Notes (public/internal), photo upload/download with validation and authorization, work completion
  (final note >= 20 characters + at least one photo), notifications, technician task list.
- Estimates: versions, immutable once submitted, customer approve/reject with reason, parallel
  decisions resolved by the database, work start blocked until a submitted estimate is approved.
- Inventory: items, replenishment history, non-negative stock (CHECK constraint), atomic and
  idempotent material write-off with a price snapshot, race-safe for the last units, low-stock
  notifications.
- Web (EN/RU): landing, sign-in, organization picker, dashboard with charts, requests list/new/detail,
  assignment panel, schedule.
- Android (Flutter): sign-in, organization choice, task list from a local database, task details,
  accept / decline / start / block / resume / complete, notes and photos with an offline queue,
  stable command ids, conflict handling, notifications, profile, EN/RU.

## Not implemented yet (do not treat as done)
- **SLA** clock, pauses, escalation (SLA-*) and the overdue queue.
- **Preventive maintenance** plans and generation (PM-*).
- **Web screens** for estimates, inventory, administration (staff, categories, skills, working hours,
  holidays), SLA reports, audit feed, notifications; customer feedback; photo upload in the web
  request form; live updates (WebSocket/SSE, API-06).
- **Android screens** for materials (the API exists), estimate total on the task, live updates;
  completion does not yet verify materials (LIFE-05 "materials correctly accounted").
- **Backend**: login rate limiting (SEC-03), request-ID structured logging (SEC-08), seed data for
  estimates / plans / SLA cases (SEED-02/03 are partially covered), editing technician skills and
  availability through the API (they exist in the database and seed only).
- **Verification**: no browser/E2E tests for web; no instrumented tests for Android; the
  `scripts/verify-all.sh` and `scripts/smoke.sh` are only partly implemented; `compose.yaml` has no
  `web` service yet (the web app runs with `bun run dev`).
- Customers see every active property of their organization (there is no customer-to-property link).
- The Android app keeps its session token in the app's private storage (sembast), not in the
  hardware-backed keystore, and allows plain HTTP for local development.

## Environment notes
- On the author's Windows machine Smart App Control blocks some unsigned native Python wheels
  (e.g. `pydantic_core`), so the backend is run and tested inside Docker; pure-logic tests run on the host.
- The Android toolchain on this machine is installed under `C:\dev` (Flutter, JDK 17, Android SDK).
