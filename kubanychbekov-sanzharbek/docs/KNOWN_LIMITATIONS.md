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
- SLA: working-time clock (hours/holidays), at-risk / overdue states, pauses while an estimate awaits approval,
  one escalation per overdue request, overdue queue.
- Preventive maintenance: weekly/monthly plans, idempotent generation of requests, last/next service per asset.
- Customer feedback (1-5 + comment, once per request) and the administrator audit feed.
- Properties and equipment (create/edit, retire, history with technicians, results, materials and photos, open work,
  last and next service), staff and roles, service categories, technician skills and availability, organization name
  and time zone, SLA report, reports with period/category/technician filters, technician load (method documented),
  approved-estimate and material totals, request-list filters by technician and dates with due-date sorting.
- Notes with public/internal visibility, materials and one unified request timeline in the web; live updates (SSE).
- Web (EN/RU): landing, sign-in, organization picker, dashboard with charts and SLA totals, requests
  list/new (with photos)/detail, assignment panel with Smart Assign, schedule, estimates, SLA badge and
  overdue queue, inventory with low stock, maintenance plans, notifications inbox, admin settings (working
  hours, holidays), customer feedback, audit log.
- Android (Flutter): sign-in, organization choice, task list from a local database, task details,
  accept / decline / start / block / resume / complete, notes and photos with an offline queue,
  stable command ids, conflict handling, materials write-off (online), approved estimate total,
  notifications, profile with own availability, SLA and earlier jobs on the equipment, EN/RU. A debug APK builds
  (see `VERIFICATION.md`).
- Compose runs `db`, `backend` and `web`; `scripts/smoke.sh` checks the real lifecycle, a 409 double
  booking and tenant isolation.

## Not implemented yet (do not treat as done)
- **Live updates** (API-06): the backend streams change hints over SSE (`GET /events`, polled every 2 s on the
  server); the web refetches the affected data on each hint and everything after a reconnect (notifications also
  refetch every 30 s). Android does not listen to the stream and refreshes on
  start, pull-to-refresh and sync.
- **Physical phone, partly confirmed.** The candidate installed the APK on a real Android phone, signed in and saw the
  task list from the real backend (reported by the candidate, not recorded by an automated check). The rest of the phone
  scenario (`docs/ANDROID_PHONE_TEST.md` steps 4-11: accept/start, note and photo, airplane mode, completion) is
  **NOT VERIFIED** on a device by the assistant: Android refused remote taps over USB (`INJECT_EVENTS`). The same steps
  are covered against the real API by `scripts/e2e_scenario.py` and `mobile/test/live`.
- **Risk register (SEC-09):** (1) per-e-mail login lockout can be used to pause an account (see below), mitigation:
  15-minute window, audit of failures, no per-IP limit yet; (2) the Android session token is in app-private storage,
  not the keystore, mitigation: sandboxed storage, token revocable server-side; (3) plain HTTP is allowed for local
  development, mitigation: used only on a local network, production would require HTTPS; (4) uploaded photos live on
  a local volume without antivirus scanning, mitigation: content-type and image validation, authorized download only.
- **Backend**: Login lockout (5 failures per e-mail in 15 minutes) is per e-mail, not per address, so someone who knows an
  e-mail can pause that account for up to 15 minutes; there is no CAPTCHA or per-IP limit.
- **LIFE-05 materials**: completion does not ask the technician to confirm "no materials used"; materials are
  accounted by the atomic write-off (see `PRODUCT_DECISIONS.md`).
- **Verification**: no browser/E2E tests for the web (the web was exercised through its API and unit tests plus manual
  browser checks); no instrumented tests for Android. The request timeline and the notes panel in the web have no
  automated UI test; the data they show is covered by the backend tests.
- **Request body limit** covers requests that declare `Content-Length`; chunked bodies without a length are not
  capped by that middleware (photo uploads are still size-checked while reading).
- **Report period** is limited to 90 days; the technician load report counts all non-cancelled assignments in the
  period, including completed ones, and caps the result at 100% (explained in the `method` field).
- **Demo data:** the demo database has no material write-offs, so the "materials used" total starts at 0 until a
  technician writes material off.
- Customers see every active property of their organization (there is no customer-to-property link).
- The Android app keeps its session token in the app's private storage (sembast), not in the
  hardware-backed keystore, and allows plain HTTP for local development.

## Environment notes
- On the author's Windows machine Smart App Control blocks some unsigned native Python wheels
  (e.g. `pydantic_core`), so the backend is run and tested inside Docker; pure-logic tests run on the host.
- The Android toolchain on this machine is installed under `C:\dev` (Flutter, JDK 17, Android SDK).
