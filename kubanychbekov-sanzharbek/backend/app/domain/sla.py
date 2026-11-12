"""SLA arithmetic in working time (SLA-01..05). Pure functions, no database.

The clock only runs inside working hours of the organization, never on holidays, and is paused
while an estimate waits for the customer. Everything is done in the organization's timezone and
returned as UTC.
"""

from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.domain.enums import Priority

# Default budgets in working hours (SLA-02).
BUDGET_HOURS = {Priority.HIGH: 8, Priority.NORMAL: 24, Priority.LOW: 48}
AT_RISK_FRACTION = 0.25  # SLA-04: at risk when 25% or less of the budget remains

Weekly = dict[int, list[tuple[time, time]]]  # weekday (0 = Monday) -> working intervals
Interval = tuple[datetime, datetime]

# SLA-01 default: Monday-Friday 09:00-18:00, weekends closed, no holidays.
DEFAULT_WEEKLY: Weekly = {d: [(time(9, 0), time(18, 0))] for d in range(5)}


def budget_minutes(priority: Priority) -> int:
    return BUDGET_HOURS[priority] * 60


def _merge(pauses: Sequence[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for start, end in sorted(pauses):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _subtract(segment: Interval, pauses: list[Interval]) -> Iterator[Interval]:
    """The parts of `segment` that are not inside any (merged, sorted) pause."""
    cursor, end = segment
    for p_start, p_end in pauses:
        if p_end <= cursor or p_start >= end:
            continue
        if p_start > cursor:
            yield cursor, p_start
        cursor = max(cursor, p_end)
        if cursor >= end:
            return
    if cursor < end:
        yield cursor, end


def working_segments(
    start: datetime,
    *,
    tz: ZoneInfo,
    weekly: Weekly,
    holidays: frozenset[date] | set[date],
    pauses: Sequence[Interval] = (),
    horizon_days: int = 800,
) -> Iterator[Interval]:
    """Consecutive working stretches from `start` onwards, with paused time cut out."""
    merged = _merge(pauses)
    day = start.astimezone(tz).date()
    for offset in range(horizon_days):
        current = day + timedelta(days=offset)
        if current in holidays:
            continue
        for s, e in sorted(weekly.get(current.weekday(), [])):
            window = (
                max(datetime.combine(current, s, tzinfo=tz), start),
                datetime.combine(current, e, tzinfo=tz),
            )
            if window[0] >= window[1]:
                continue
            for a, b in _subtract(window, merged):
                yield a.astimezone(UTC), b.astimezone(UTC)


def working_minutes(
    start: datetime,
    end: datetime,
    *,
    tz: ZoneInfo,
    weekly: Weekly,
    holidays: frozenset[date] | set[date] = frozenset(),
    pauses: Sequence[Interval] = (),
) -> int:
    """Working minutes in [start, end), skipping closed hours, holidays and paused time."""
    if end <= start:
        return 0
    total = 0.0
    for a, b in working_segments(
        start,
        tz=tz,
        weekly=weekly,
        holidays=holidays,
        pauses=pauses,
        horizon_days=(end - start).days + 2,
    ):
        if a >= end:
            break
        total += (min(b, end) - a).total_seconds()
    return int(total // 60)


def deadline(
    start: datetime,
    minutes: int,
    *,
    tz: ZoneInfo,
    weekly: Weekly,
    holidays: frozenset[date] | set[date] = frozenset(),
    pauses: Sequence[Interval] = (),
) -> datetime | None:
    """The instant when `minutes` of working time have passed since `start` (None if never)."""
    left = timedelta(minutes=minutes)
    if left <= timedelta(0):
        return start
    for a, b in working_segments(start, tz=tz, weekly=weekly, holidays=holidays, pauses=pauses):
        length = b - a
        if length >= left:
            return a + left
        left -= length
    return None


def sla_state(budget: int, used: int) -> tuple[str, int]:
    """Return (state, remaining_minutes). `remaining` is negative once the SLA is overdue."""
    remaining = budget - used
    if remaining < 0:
        return "OVERDUE", remaining
    if remaining <= budget * AT_RISK_FRACTION:
        return "AT_RISK", remaining
    return "ON_TRACK", remaining


def remaining_after_priority_change(new_budget: int, used: int) -> tuple[str, int]:
    """SLA-05: new budget minus the working time already used."""
    return sla_state(new_budget, used)
