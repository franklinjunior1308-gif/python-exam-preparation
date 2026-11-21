# Bookify

Booking management SaaS for small businesses (barbershops, salons, tutors). Flask · SQLAlchemy · SQLite · Jinja2 · custom CSS.

## Local installation (Windows PowerShell)

```powershell
cd bookify
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # then set SECRET_KEY
flask --app wsgi db upgrade     # create the database (instance/bookify.sqlite)
python seed.py                  # fake demo data
flask --app wsgi run            # http://127.0.0.1:5000
```

macOS/Linux: `source .venv/bin/activate` and `cp .env.example .env`.

## Demo accounts (fake data, password for all: `Demo1234!`)

| Role | Email | Notes |
|---|---|---|
| Admin | `admin@demo.test` | Sharp & Co Barbershop |
| Admin | `admin2@demo.test` | Glow Beauty Studio (use to test business isolation) |
| Staff | `dan@demo.test` (also `mia@`, `leo@`) | Sharp & Co staff |
| Customer | `customer@demo.test` (also `customer2@`) | has upcoming, completed and cancelled bookings |

`python seed.py --reset` wipes all data and reseeds. **Never use these accounts in production.**

## Tests

```powershell
pytest            # 54 tests, ~50 s (most of the time is password hashing)
```

Covers registration, login, invalid credentials, duplicate emails, service validation, business isolation, staff/role authorization, slot calculation, overlapping bookings, **concurrent booking (threads against a file-based SQLite DB)**, cancellation rules, history, past-date rejection, CSRF, and that every page renders.

## How double booking is prevented

`BookingManager.create_booking` never trusts the browser's slot list:

1. Re-validates everything server-side (future time, service active, staff qualified, time is a real slot inside working hours, correct duration).
2. Opens the write transaction with SQLite `BEGIN IMMEDIATE` **before** reading existing bookings. Concurrent requests queue on the database write lock (15 s busy timeout), so check-then-insert is atomic across threads and processes. On PostgreSQL/MySQL it uses `SELECT … FOR UPDATE` on the staff row instead.
3. A partial unique index `uq_bookings_active_slot (staff_id, start_time) WHERE status != 'cancelled'` is a last-resort DB guard.

The overlap test was verified by temporarily disabling step 2: it then fails (two bookings succeed). Cancelled bookings free their slot.

## Project layout

```
app/
  __init__.py        application factory, error handlers, security headers
  config.py          Development / Testing / Production config (env based)
  models.py          User, Business, Service, StaffMember, WorkSchedule, Booking, Notification (+ staff_services)
  services/          AvailabilityService, BookingManager, NotificationService
  blueprints/        public, auth, customer, admin, staff
  templates/ static/
migrations/          Alembic migrations (Flask-Migrate)
tests/  seed.py  wsgi.py
```

Times are stored as naive UTC and displayed in each business's time zone. Slot interval defaults to 30 minutes. Customers may cancel until 2 hours before the start; admins may cancel any non-completed booking at any time.

## PythonAnywhere deployment

1. Create a free/paid account, open a **Bash console** and clone the repo:
   `git clone https://github.com/<you>/<repo>.git && cd <repo>/bookify`
2. `mkvirtualenv bookify --python=python3.11` then `pip install -r requirements.txt`
3. Create `.env` in the `bookify` folder (never commit it):
   ```
   FLASK_ENV=production
   SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))">
   DEFAULT_TIMEZONE=Europe/London
   ```
4. `flask --app wsgi db upgrade` (optionally `python seed.py` for a demo)
5. **Web** tab → *Add a new web app* → Manual configuration → Python 3.11. Set the virtualenv path to `/home/<user>/.virtualenvs/bookify`, then edit the WSGI file:
   ```python
   import sys
   path = "/home/<user>/<repo>/bookify"
   if path not in sys.path:
       sys.path.insert(0, path)
   from wsgi import app as application
   ```
6. Static files: URL `/static/` → directory `/home/<user>/<repo>/bookify/app/static`.
7. Enable **Force HTTPS** on the Web tab (production cookies are `Secure`), then **Reload**.
8. Updating: `git pull && flask --app wsgi db upgrade`, then Reload.

Production mode refuses to start without a strong `SECRET_KEY`. Back up `instance/bookify.sqlite` regularly. For real traffic, move to PostgreSQL via `DATABASE_URL`.

## Feature status

**Implemented & tested:** business and customer registration; secure login (hashed passwords, CSRF, safe `next` redirects, secure cookie settings); role-based access (admin/staff/customer) with per-business data isolation; service CRUD with deactivate; staff management (accounts, qualifications, deactivate); weekly schedules; slot generation; booking, cancellation, completion; price/duration snapshots; customer dashboard and history; staff dashboard; admin dashboard stats, weekly calendar, booking list; internal notifications; custom 400/403/404/500 pages; responsive UI with loading and empty states.

**Verified manually in a browser:** login, slot loading and booking on the booking page (desktop-width pane). **Not verified:** real mobile devices, cross-browser, screen readers, PythonAnywhere deployment (instructions are untested), PostgreSQL path.

**Not implemented (by design or yet):** payments, email/SMS/WhatsApp, password reset / email verification, staff time-off and breaks, multiple shifts per day, rescheduling, multiple admins per business, rate limiting / lockout on login, audit log, i18n, per-business slot interval UI, subscription billing. Staff cannot yet change their own password (admins set a temporary one).
