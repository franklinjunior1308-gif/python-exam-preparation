# Product decisions

## Original workflow improvement (WEB-09): Smart Assign

### The user problem
To schedule a request, a dispatcher has to find a technician who (a) holds every skill the
category needs, (b) is active and on shift, (c) is not away, (d) has no overlapping booking, and
(e) is free near the time the customer asked for. Doing that by hand means opening a schedule,
comparing hours and guessing, and the usual outcome is a `409 schedule_conflict` after typing a
time. It is the slowest and most error-prone step between "triaged" and "scheduled".

### What it does
On the page of a **triaged** request, dispatchers and administrators see a *Smart Assign* card
(`web/components/AssignPanel.tsx`) with up to three ready-to-apply proposals:

- Candidates are technicians that are active and hold **all** skills of the request's category.
- For each of them the backend finds the **earliest free visit** of the category's standard
  duration: inside weekly working hours, outside absences, not overlapping any active booking,
  on a 30-minute grid in the organization's timezone, at least one hour from now, looking up to
  14 days ahead (`earliest_slot` in `backend/app/domain/scheduling.py`).
- If the customer entered a preferred visit window, a slot **inside** that window is preferred
  and the card says whether the proposal is inside or outside it.
- Proposals are ranked: inside the preferred window first, then earliest start, then lightest
  weekly load, then name. The first one is marked "Best match".
- One click applies a proposal. It is sent through the normal `POST /requests/{id}/assignments`
  command, so every rule and the database overlap guard still run; a suggestion can never create
  a booking that manual assignment would reject.
- A manual fallback ("Choose technician and time manually") lists every technician for a chosen
  window with the exact reasons someone is unavailable (missing skill, off shift, away, already
  booked, ...).

API: `GET /api/v1/requests/{id}/suggestions` (staff only, tenant-scoped, empty unless the request is
triaged).

### How it is verified
- `backend/tests/test_scheduling_rules.py`: 6 unit tests for `earliest_slot` (opening time, busy gaps,
  touching bookings, half-hour rounding, rollover to the next workday, weekends, absences,
  deadline and horizon).
- `backend/tests/test_scheduling_api.py` (PostgreSQL): only qualified technicians are proposed; the
  proposal can be applied; the next request gets a later slot because the first one is now busy;
  customers get 403, other organizations get 404, and an already scheduled request gets no proposals.
- Manual check in the browser (see `VERIFICATION.md`): request #28 was offered Azamat Kenzhebaev on
  13 Nov 09:00-10:00, one click moved it to *Scheduled*, and the booking appeared in the schedule.

### Trade-offs
1. **Earliest slot, not global optimization.** Each technician is judged on their own; we do not
   rebalance other bookings to make room. This keeps answers instant and explainable, at the cost
   of not finding a perfect plan for a busy day.
2. **Suggestions are not reserved.** Two dispatchers can see the same proposal; the second one to
   apply it gets a clear `409` from the database guard. Holding slots would need expiry logic and
   would block colleagues, which is worse for a small team.
3. **No travel time or geography.** Maps and routing services are excluded by PROD-05 (no paid or
   external services), so distance is ignored and only time and skills are considered.
4. **Fixed constants** (30-minute grid, 14-day horizon, one-hour lead time) instead of settings.
   They suit the default demo organization; making them configurable is a small follow-up.
5. **Load is only a tie-breaker.** Starting earlier beats a lighter load, because customers
   notice waiting more than dispatchers notice uneven workload.

## Other decisions worth knowing
- **Authorization and tenancy live on the server.** Every query is scoped by organization and the
  role is re-checked per request; composite foreign keys also make cross-organization links
  impossible in the database.
- **Invariants are enforced by PostgreSQL**, not by code alone: an exclusion constraint on
  `tstzrange(start_at, end_at, '[)')` per technician for active bookings, one active booking per
  request, CHECK constraints for text lengths and visit duration.
- **Web uses a backend-for-frontend proxy.** The access token sits in an httpOnly cookie that page
  scripts cannot read; state-changing calls need a custom header (CSRF guard).
- **Time is stored in UTC and shown in the organization's timezone**; the web converts typed
  wall-clock times with the organization's zone, never the browser's.
