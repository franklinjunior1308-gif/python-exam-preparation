"""Recurrence dates of preventive-maintenance plans (PM-01, PM-02). Pure functions."""

import calendar
from datetime import date, timedelta
from enum import StrEnum

MAX_OCCURRENCES = 400  # safety cap per plan and run


class Frequency(StrEnum):
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


def _add_months(first: date, months: int) -> date:
    """Same day of month, clamped to the month's length (Jan 31 + 1 month = Feb 28/29)."""
    index = first.month - 1 + months
    year = first.year + index // 12
    month = index % 12 + 1
    day = min(first.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def occurrences(first: date, frequency: Frequency, as_of: date) -> list[date]:
    """Every event date from `first` up to and including `as_of`.

    Months are always counted from the first date, so Jan 31 gives Feb 28 and then Mar 31
    (not Mar 28): the series never drifts.
    """
    result: list[date] = []
    step = 0
    while len(result) < MAX_OCCURRENCES:
        if frequency == Frequency.WEEKLY:
            current = first + timedelta(weeks=step)
        else:
            current = _add_months(first, step)
        if current > as_of:
            break
        result.append(current)
        step += 1
    return result


def next_occurrence(first: date, frequency: Frequency, after: date) -> date:
    """The first event date strictly after `after`."""
    step = 0
    while True:
        current = (
            first + timedelta(weeks=step)
            if frequency == Frequency.WEEKLY
            else _add_months(first, step)
        )
        if current > after:
            return current
        step += 1
