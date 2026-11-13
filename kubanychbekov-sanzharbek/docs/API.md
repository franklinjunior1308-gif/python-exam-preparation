# API overview and examples

Base URL: `http://localhost:8000/api/v1`. OpenAPI: `http://localhost:8000/docs`.
Errors are always `{"error": {"code": "...", "message": "...", "details": [...]}}`.
Statuses: `400/401/403/404/409/422` (+`413` for oversized uploads). All protected calls need
`Authorization: Bearer <token>` and, inside an organization, `X-Organization-Id: <id>`.

| Area | Endpoints |
|---|---|
| Health | `GET /health/live`, `GET /health/ready` (503 when the database is down) |
| Auth & memberships | `POST /auth/login`, `POST /auth/logout`, `GET /me` |
| Organization & staff | `GET/PUT /settings/organization`, `GET/POST /users`, `PUT /users/{id}`, `GET/PUT /settings/working-hours`, `POST/DELETE /settings/holidays` |
| Categories & skills | `GET/POST /categories`, `PUT /categories/{id}`, `GET /technicians`, `PUT /technicians/{id}/profile` |
| Properties & equipment | `GET/POST /properties`, `PUT /properties/{id}`, `GET/POST /assets`, `PUT /assets/{id}`, `GET /assets/{id}/history`, `GET /assets/{id}/summary` |
| Requests & lifecycle | `POST/GET /requests` (filters, sorting, paging), `GET /requests/{id}`, `GET /requests/{id}/history`, `POST /requests/{id}/transitions`, `POST /requests/{id}/complete` |
| Scheduling | `GET /schedule?from&to`, `GET /requests/{id}/candidates`, `GET /requests/{id}/suggestions`, `GET/POST /requests/{id}/assignments`, `PATCH /assignments/{id}`, `POST /assignments/{id}/unassign`, `POST /assignments/{id}/decline` |
| Estimates | `GET/POST /requests/{id}/estimates`, `PUT /estimates/{id}`, `POST /estimates/{id}/submit`, `POST /estimates/{id}/decision`, `POST /estimates/{id}/withdraw` |
| Inventory & materials | `GET/POST /inventory`, `POST /inventory/{id}/replenish`, `GET/POST /requests/{id}/materials` |
| SLA | `GET /sla/overdue`, SLA block on every request, `python -m app.sla_scan` |
| Preventive maintenance | `GET/POST /maintenance-plans`, `POST /maintenance-plans/{id}/disable`, `GET /maintenance-plans/{id}/requests`, `POST /maintenance/generate`, `python -m app.pm_generate` |
| Notes, photos, feedback | `GET/POST /requests/{id}/notes`, `GET/POST /requests/{id}/attachments`, `GET /attachments/{id}/file`, `GET/POST /requests/{id}/feedback` |
| Technician app | `GET /my/tasks` (with SLA and earlier jobs on the equipment), `GET /my/availability` |
| Notifications & live updates | `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all`, `GET /events` (SSE) |
| Reports & audit | `GET /reports/summary`, `GET /reports/sla`, `GET /audit` |

## Examples

### Sign in
```http
POST /api/v1/auth/login
{"email": "dispatcher.a@fixflow.test", "password": "Demo-2345!"}

200 {"access_token": "eyJ...", "token_type": "bearer", "expires_at": "2026-11-12T22:20:00Z"}
```
A wrong password is `401 {"error": {"code": "invalid_credentials", ...}}`.

### Create a request (customer)
```http
POST /api/v1/requests          X-Organization-Id: 1
{"title": "Ventilation fan does not work",
 "description": "The extractor fan makes no sound and no air flows out.",
 "category_id": 1, "property_id": 4, "priority": "HIGH"}

201 {"id": 54, "status": "SUBMITTED", "allowed_actions": ["CANCELED"], ...}
```
A title shorter than 5 characters is `422 validation_error`.

### Assign a technician (dispatcher) and a conflict
```http
POST /api/v1/requests/28/assignments
{"technician_id": 2, "start_at": "2026-11-16T04:00:00Z", "end_at": "2026-11-16T06:00:00Z"}
201 {"id": 29, "status": "SCHEDULED", ...}        # request 28 becomes SCHEDULED

POST /api/v1/requests/30/assignments                # same technician, overlapping time
{"technician_id": 2, "start_at": "2026-11-16T05:00:00Z", "end_at": "2026-11-16T07:00:00Z"}
409 {"error": {"code": "schedule_conflict", "message": "..."}}
```
`[04:00,06:00)` and `[06:00,08:00)` do not overlap and are both accepted. Repeating the first call
returns `200` with the same assignment (idempotent).

### Smart Assign
```http
GET /api/v1/requests/28/suggestions
200 [{"technician_id": 2, "full_name": "Azamat Kenzhebaev", "start_at": "2026-11-13T03:00:00Z",
      "end_at": "2026-11-13T04:00:00Z", "load_percent": 9, "within_desired_window": null,
      "is_best": true}, ...]
```

### Offline replay of a note (idempotency)
```http
POST /api/v1/requests/5/notes
{"body": "Pressure is low", "visibility": "internal", "client_command_id": "9f1c...32 hex"}
201 {"id": 12, ...}

# the phone never received the answer and sends the same command again:
POST /api/v1/requests/5/notes   (same body)
200 {"id": 12, ...}              # same note, no duplicate is created
```
The same `client_command_id` with a different body is `409 idempotency_conflict`. If the technician
was unassigned meanwhile, the answer is `409 assignment_changed` and the app keeps the draft.

### Upload a photo
```http
POST /api/v1/requests/5/attachments       (multipart/form-data)
file=<image>, client_command_id=<hex>, purpose=after
201 {"id": 3, "content_type": "image/png", "width": 1200, "height": 800, ...}
```
Text disguised as `photo.png` is `422 invalid_image`; more than 10 MiB is `413 file_too_large`.

### Complete the work (technician)
```http
POST /api/v1/requests/5/complete
{"summary": "Replaced the filter and tested the unit.", "client_command_id": "<hex>"}
200 {"status": "COMPLETED", ...}
```
Needs a summary of at least 20 characters (`422 summary_too_short`) and at least one photo uploaded by
the technician (`422 photo_required`). Repeating the same command returns the same result.

### Customer feedback (COMM-07)
```http
GET  /api/v1/requests/5/feedback          -> 200 null | {"id", "request_id", "author_user_id", "rating", "comment", "created_at"}
POST /api/v1/requests/5/feedback
{"rating": 4, "comment": "Fast and tidy"}  -> 201 {...}
```
Only the customer who created the request may rate it (`403 forbidden`), only after it is `COMPLETED` or `CLOSED`
(`409 request_not_finished`), once (`409 feedback_exists`, enforced by a unique constraint, so a double click is
safe). Rating is 1-5 (`422`). Anyone who can see the request can read the rating.

### Audit feed (ORG-05, administrators only)
```http
GET /api/v1/audit?limit=50&offset=0&action=inventory.&object_type=service_request
200 {"items": [{"id", "created_at", "actor_user_id", "actor_name", "action", "object_type", "object_id",
                "before", "after"}], "total": 19, "limit": 50, "offset": 0}
```
Newest first, scoped to the organization in `X-Organization-Id`; `action` is a prefix filter. Other roles get
`403 forbidden`. `limit` is 1-200.

### Technician skills and weekly hours (ORG-01, administrators only)
```http
GET /api/v1/technicians                      (staff) -> [{"id", "user_id", "full_name", "email", "is_active",
                                                         "skills": ["hvac"], "availability": [{"weekday": 0, "start_time": "09:00:00", "end_time": "18:00:00"}], "load_percent"}]
PUT /api/v1/technicians/{id}/profile
{"skills": ["hvac", "electrical"], "availability": [{"weekday": 0, "start_time": "08:00:00", "end_time": "17:00:00"}], "is_active": true}
200 <the technician as above>
```
Replaces skills and weekly intervals as a whole. Skills are trimmed, lower-cased and de-duplicated; `weekday` is 0
(Monday) to 6; intervals must end after they start and must not overlap on one day (`422`). `is_active` is optional.
Other roles get `403`, another organization's technician `404`. The change is written to the audit feed
(`technician.profile_updated`) and Smart Assign uses it immediately.

### Request IDs and the login lockout (SEC-08, SEC-03)
Every response has `X-Request-ID` (a caller-supplied value of 8-64 letters/digits/`._-` is kept, anything else is
replaced) and error bodies carry `error.request_id`. The server writes one JSON log line per request
(`request_id`, `method`, `path`, `status`, `duration_ms`); bodies, passwords and tokens are never logged.
Five failed sign-ins for one e-mail within 15 minutes answer `429 too_many_attempts` (also for the correct password)
until the oldest failure leaves the window. Limits: `LOGIN_MAX_FAILURES`, `LOGIN_WINDOW_MINUTES`.

### Staff and roles (ORG-04, AUTH-05, administrators only)
```http
GET  /api/v1/users                     -> [{"id", "email", "full_name", "role", "is_active", "technician_id"|null}]
POST /api/v1/users
{"email": "a@b.kg", "full_name": "Aida K.", "role": "technician", "password": "Start-Pass-12"}   -> 201 <user>
PUT  /api/v1/users/{id}
{"role": "dispatcher", "is_active": false}   (both optional)                                    -> 200 <user>
```
`is_active` is the membership in this organization. Passwords need 10+ characters with a letter and a digit (`422`).
An e-mail that already has an account in another organization only gains a membership (its password is unchanged).
Errors: `409 already_member`, `409 last_admin` (the organization must keep one active administrator),
`409 technician_has_active_assignments`, `404 user_not_found` (also for other organizations), `403 forbidden`.
Deactivating a member revokes all of their sessions at once. Audited as `user.created`, `user.role_changed`,
`user.deactivated`, `user.activated`.

### Categories admin (ORG-03, administrators only)
```http
POST /api/v1/categories
{"name": "Plumbing", "description": "Pipes", "default_duration_min": 90, "required_skills": ["plumbing"]}   -> 201
PUT  /api/v1/categories/{id}      same fields + "is_active": false   -> 200
CategoryOut: {"id", "name", "description", "default_duration_min", "required_skills", "is_active"}
```
Duration is 5-480 minutes (`422`); the name is unique per organization (`409 category_name_taken`); skills are
lower-cased and de-duplicated. A disabled category stays on existing requests but is refused for new ones
(`422 category_inactive`). `GET /categories?include_inactive=true` (admin/dispatcher) lists disabled ones too.
Audited as `category.created` / `category.updated`.

### Live updates (API-06)
```http
GET /api/v1/events        Authorization: Bearer <token>   X-Organization-Id: <id>      -> text/event-stream
retry: 3000
: connected

event: changed
data: {"scope": "requests" | "assignments" | "notifications", "request_id": 5 | null, "at": "2026-11-13T05:00:00+00:00"}

: keepalive
```
Hints only: ids, never data, so the client refetches through the normal permission-checked endpoints.
Customers and technicians only get hints for requests they can see; notifications only for their recipient.
The server checks for new audit/notification rows every 2 s (`EVENTS_POLL_SECONDS`), sends `: keepalive` every
15 s (`EVENTS_KEEPALIVE_SECONDS`) and closes the stream when the session is revoked or expires. `401` without a
token, `400` without `X-Organization-Id`.

### SLA report (WEB-04, dispatchers and administrators)
```http
GET /api/v1/reports/sla?days=30     (1-365)
200 {"period_days": 30, "total": 12, "on_time": 10, "late": 2, "avg_resolution_minutes": 310, "escalated": 1,
     "by_priority": [{"priority": "HIGH", "total": 4, "late": 1}]}
```
Counts requests completed in the period and judges each by its SLA budget in working time (late = over budget at
the moment of completion). `avg_resolution_minutes` is working minutes and `null` when nothing was completed;
`escalated` counts escalations raised in the period. Customers and technicians get `403`.

### Properties and equipment (ASSET-01..05)
```http
POST /api/v1/properties   {"name", "address", "contact_instructions"?, "is_active"?}        -> 201 (dispatcher/admin)
PUT  /api/v1/properties/{id}  same fields; is_active=false hides it from new requests, history stays
GET  /api/v1/properties?include_inactive=true            (staff only sees inactive ones)
POST /api/v1/assets  {"property_id", "code", "name", "asset_type", "serial_number"?, "installed_on"?,
                      "status": "ACTIVE|OUT_OF_SERVICE|RETIRED", "notes"?}                  -> 201
PUT  /api/v1/assets/{id}   same fields without "code" (the code is fixed)
GET  /api/v1/assets/{id}/history   -> [{"request_id", "title", "status", "priority", "created_at", "completed_at",
                                        "technicians": [name], "result", "materials": [{"item_name", "quantity", "total_cents"}],
                                        "attachments": [{"id", "purpose"}]}]
GET  /api/v1/assets/{id}/summary   open requests, last completed service, next planned maintenance
```
Errors: `409 asset_code_taken`, `409 asset_retired` (retired equipment cannot be reactivated; new maintenance plans are
refused), `404` for another organization's property/equipment, `403` for customers and technicians (history is staff-only).
Audited as `property.created/updated` and `asset.created/updated/retired`.

### Request list filters, reports and organization settings (final audit additions)
```http
GET /api/v1/requests?technician_id=4&created_from=2026-11-01&created_to=2026-11-14&sort_by=due_at&descending=false
```
`sort_by` is `created_at`, `priority`, `id` or `due_at` (SLA deadline, earliest first; finished or paused requests
last). Dates are whole days in the organization time zone. `page_size` is at most 100.
```http
GET /api/v1/reports/summary?date_from=2026-11-01&date_to=2026-11-14&category_id=2&technician_id=4
200 {"total", "open", "overdue", "in_progress", "completed_in_period", "by_status", "by_priority", "by_category",
     "daily": [{"date", "created", "completed"}], "upcoming_visits": [{"request_id", "title", "technician", "start_at", "end_at"}],
     "technician_load": {"percent", "scheduled_minutes", "available_minutes", "technicians", "method"},
     "approved_estimates_cents", "approved_estimates_count", "materials_cost_cents", "date_from", "date_to"}
```
The period is `days` (default 14) or `date_from`..`date_to`, at most 90 local days (`422 invalid_period`,
`period_too_long`). `technician_load` is scheduled minutes divided by the working minutes of the active technicians
(availability minus absences, organization time zone), capped at 100; its `method` field says so. Approved
estimates are quotes decided in the period, not revenue. `overdue`, `technician_load` and `materials_cost_cents` are
`null` for customers and technicians, who only see aggregates of their own requests.
```http
GET /api/v1/settings/organization -> {"id", "name", "timezone"}
PUT /api/v1/settings/organization {"name": "AIT Facility", "timezone": "Asia/Bishkek"}   (administrators only)
```
Unknown IANA zones are `422`. Stored instants stay in UTC; the zone changes display, working days and SLA from then on.
Every response carries `X-Request-ID`; request bodies over 1 MiB (11 MiB for photo uploads) are `413 body_too_large`.
A rework request (`COMPLETED -> REOPENED`) notifies the dispatchers/administrators and the technician who did the work.
Logout and deactivating a member write `auth.session_revoked` / `auth.sessions_revoked` to the audit feed.
