"""Pure scheduling rules (no database): visit window checks, skills, overlap, load.

Keeping these free of I/O makes them easy to unit-test; the database still enforces the
hard invariants (overlap exclusion constraint) because two requests can race.
"""

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

MIN_VISIT = timedelta(minutes=30)

Weekly = dict[int, list[tuple[time, time]]]  # weekday (0=Mon) -> [(start, end), ...]


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """Half-open intervals [start, end): touching ends do not overlap."""
    return a_start < b_end and b_start < a_end


def missing_skills(required: Iterable[str], have: Iterable[str]) -> list[str]:
    owned = {s.strip().lower() for s in have}
    return [s for s in required if s.strip().lower() not in owned]


def window_problems(
    start_at: datetime,
    end_at: datetime,
    *,
    now: datetime,
    tz: ZoneInfo,
    weekly: Weekly,
    absences: Sequence[tuple[datetime, datetime]],
) -> list[str]:
    """Return machine-readable problem codes for a proposed visit; empty list means fine."""
    if end_at <= start_at:
        return ["invalid_range"]
    problems: list[str] = []
    if end_at - start_at < MIN_VISIT:
        problems.append("too_short")
    if start_at < now:
        problems.append("in_past")

    local_start = start_at.astimezone(tz)
    local_end = end_at.astimezone(tz)
    intervals = weekly.get(local_start.weekday(), [])
    same_day = local_start.date() == local_end.date()
    inside = same_day and any(
        s <= local_start.time() and local_end.time() <= e for s, e in intervals
    )
    if not inside:
        problems.append("outside_availability")

    if any(overlaps(start_at, end_at, a_start, a_end) for a_start, a_end in absences):
        problems.append("absent")
    return problems


def available_minutes(
    week_start: datetime,
    week_end: datetime,
    *,
    tz: ZoneInfo,
    weekly: Weekly,
    absences: Sequence[tuple[datetime, datetime]],
) -> int:
    """Working minutes inside [week_start, week_end) minus absences, in the org timezone."""
    total = 0
    day = week_start.astimezone(tz).date()
    last = (week_end - timedelta(seconds=1)).astimezone(tz).date()
    while day <= last:
        for s, e in weekly.get(day.weekday(), []):
            start = datetime.combine(day, s, tzinfo=tz)
            end = datetime.combine(day, e, tzinfo=tz)
            minutes = (end - start).total_seconds() / 60
            for a_start, a_end in absences:
                lo, hi = max(start, a_start), min(end, a_end)
                if lo < hi:
                    minutes -= (hi - lo).total_seconds() / 60
            total += max(0, round(minutes))
        day += timedelta(days=1)
    return total


def earliest_slot(
    *,
    duration: timedelta,
    not_before: datetime,
    horizon_days: int,
    tz: ZoneInfo,
    weekly: Weekly,
    absences: Sequence[tuple[datetime, datetime]],
    busy: Sequence[tuple[datetime, datetime]],
    must_end_by: datetime | None = None,
    step: timedelta = timedelta(minutes=30),
) -> tuple[datetime, datetime] | None:
    """First free visit of `duration` that fits working hours, absences and existing bookings.

    Candidate starts lie on a `step` grid (default 30 min) in the organization's timezone, so
    suggestions look like 10:00 or 10:30, never 10:07. Returns None when nothing fits within
    `horizon_days` (or before `must_end_by`).
    """
    duration = max(duration, MIN_VISIT)
    local_from = not_before.astimezone(tz)
    day = local_from.date()
    blocked = [*absences, *busy]
    step_s = int(step.total_seconds())

    for offset in range(horizon_days + 1):
        current = day + timedelta(days=offset)
        for s, e in sorted(weekly.get(current.weekday(), [])):
            window_start = datetime.combine(current, s, tzinfo=tz)
            window_end = datetime.combine(current, e, tzinfo=tz)
            start = max(window_start, local_from)
            # round up to the next grid point counted from the start of the working window
            gap = int((start - window_start).total_seconds())
            if gap % step_s:
                start += timedelta(seconds=step_s - gap % step_s)
            while start + duration <= window_end:
                end = start + duration
                if must_end_by is not None and end > must_end_by:
                    return None
                if not any(overlaps(start, end, b_start, b_end) for b_start, b_end in blocked):
                    return start.astimezone(UTC), end.astimezone(UTC)
                start += step
    return None


def load_percent(assigned_minutes: int, available: int) -> int:
    """Workload = scheduled minutes / available working minutes (REPORT-03).

    Capped at 100 because an assignment may sit partly outside normal hours; without any
    availability the load is reported as 0 and the technician simply cannot be booked.
    """
    if available <= 0:
        return 0
    return min(100, round(assigned_minutes * 100 / available))
