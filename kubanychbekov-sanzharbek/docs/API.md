# API overview and examples

Base URL: `http://localhost:8000/api/v1`. OpenAPI: `http://localhost:8000/docs`.
Errors are always `{"error": {"code": "...", "message": "...", "details": [...]}}`.
Statuses: `400/401/403/404/409/422` (+`413` for oversized uploads). All protected calls need
`Authorization: Bearer <token>` and, inside an organization, `X-Organization-Id: <id>`.

| Area | Endpoints |
|---|---|
| Health | `GET /health/live`, `GET /health/ready` (503 when the database is down) |
| Auth & memberships | `POST /auth/login`, `POST /auth/logout`, `GET /me` |
| Catalog | `GET /categories`, `GET /properties`, `GET /assets?property_id=` |
| Requests & lifecycle | `POST/GET /requests`, `GET /requests/{id}`, `GET /requests/{id}/history`, `POST /requests/{id}/transitions`, `POST /requests/{id}/complete` |
| Scheduling | `GET /technicians`, `GET /schedule?from&to`, `GET /requests/{id}/candidates`, `GET /requests/{id}/suggestions`, `GET/POST /requests/{id}/assignments`, `PATCH /assignments/{id}`, `POST /assignments/{id}/unassign`, `POST /assignments/{id}/decline` |
| Notes & files | `GET/POST /requests/{id}/notes`, `GET/POST /requests/{id}/attachments`, `GET /attachments/{id}/file` |
| Technician | `GET /my/tasks` |
| Notifications | `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all` |
| Reports | `GET /reports/summary?days=` |

Not implemented yet: estimates, inventory, preventive maintenance, SLA endpoints, audit feed,
organization administration (see `KNOWN_LIMITATIONS.md`).

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
