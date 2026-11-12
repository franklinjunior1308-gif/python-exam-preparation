# Architecture

## Components

```
Android (Flutter) ──HTTPS/HTTP──┐
                                ├──> FastAPI (/api/v1) ──> PostgreSQL 17
Browser ──> Next.js (/bff) ─────┘            │
                                             └──> upload volume (photos)
```

- **Backend** (`backend/`): FastAPI, SQLAlchemy 2, Alembic, Pydantic. Layers: `api` (routing, auth
  dependencies) -> `services` (use cases and transactions) -> `domain` (pure rules: lifecycle,
  scheduling) -> `models` (tables). All times are stored as UTC.
- **Web** (`web/`): Next.js 16 App Router, TypeScript strict, React Query. The browser never calls
  the API directly: it calls `/bff/*`, a route handler that attaches the session cookie.
- **Android** (`mobile/`): Flutter, `provider` + `ChangeNotifier`, `sembast` for local storage.
- **Data**: one PostgreSQL database; photos are files on a persistent volume (`UPLOAD_DIR`).

## Organization isolation (PROD-03, ROLE-02/04)

1. Every protected request carries a token and an explicit `X-Organization-Id`.
2. `get_org_context` verifies on the server, for every request, that the user has an **active
   membership** in that active organization; otherwise `403 not_a_member`.
3. All queries filter by `organization_id`; rows of other organizations (or of other customers) are
   answered with `404`, so existence is not revealed.
4. The database backs this up: composite foreign keys `(organization_id, id)` make a request,
   asset, category, assignment or note impossible to link across organizations.

## Authentication

Passwords use Argon2. A login creates a row in `user_sessions` and returns a short-lived JWT that only
carries the session id; the server checks the row (not revoked, not expired, user active) on every
call, so logout and account disabling take effect immediately. Failed logins are audited without the
password. The web stores the token in an httpOnly cookie and sends a custom header on state-changing
calls (CSRF guard); the Android app keeps it in its private app storage.

## Concurrency and invariants (SCHED-03/04, LIFE-08)

- **Schedule**: `assignments` has an exclusion constraint
  `EXCLUDE USING gist (technician_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&) WHERE status IN
  (active states)`. Two parallel bookings of one technician cannot both commit; the loser becomes
  `409 schedule_conflict`. A partial unique index allows one active assignment per request.
- **Request status**: a compare-and-set `UPDATE ... WHERE status = :previous`; if nobody matched, the
  transaction is rolled back with `409 state_conflict`. History and audit rows are written in the same
  transaction as the change.
- None of this relies on process memory, so several API workers are safe.

## Idempotency (API-03/04, MOB-06)

Notes, photos and completion carry a client-chosen `client_command_id`, unique per organization in
the database. The same command with the same content returns the original result (`200`); the same id
with different content is `409 idempotency_conflict`. Assignment is idempotent by value: repeating the
same booking returns the existing one. This survives restarts and offline retries.

## Files (COMM-05/06)

Uploads are validated by decoding the bytes (JPEG/PNG/WebP, 10 MiB, side and pixel limits), stored
under a server-generated name, and downloaded only through `GET /attachments/{id}/file` after the same
visibility checks as the request (customers cannot fetch files attached to internal notes). A failed
upload removes the file it wrote.

## Offline Android (MOB-03..08)

Reads come from the local database first. Notes and photos entered offline become queue items with
a stable command id; a sync round delivers them in order, stops at the first network failure, marks a
refused item as *failed* and a "job changed while offline" response (`assignment_changed`,
`request_closed`) as *conflict*. Conflicts and failures are never deleted automatically. Accept /
start / complete need the server and are disabled offline with an explanation.
