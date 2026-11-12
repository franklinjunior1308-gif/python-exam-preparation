from datetime import date

from app.domain.maintenance import Frequency, next_occurrence, occurrences


def test_weekly_events_include_the_first_and_the_as_of_date():
    days = occurrences(date(2026, 11, 2), Frequency.WEEKLY, date(2026, 11, 23))
    assert days == [date(2026, 11, 2), date(2026, 11, 9), date(2026, 11, 16), date(2026, 11, 23)]


def test_nothing_is_generated_for_the_future():
    assert occurrences(date(2026, 12, 1), Frequency.WEEKLY, date(2026, 11, 30)) == []
    assert occurrences(date(2026, 12, 1), Frequency.MONTHLY, date(2026, 11, 30)) == []


def test_monthly_events_keep_the_day_of_month():
    days = occurrences(date(2026, 1, 15), Frequency.MONTHLY, date(2026, 4, 20))
    assert days == [date(2026, 1, 15), date(2026, 2, 15), date(2026, 3, 15), date(2026, 4, 15)]


def test_monthly_events_clamp_to_short_months_without_drifting():
    days = occurrences(date(2026, 1, 31), Frequency.MONTHLY, date(2026, 4, 30))
    assert days == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]
    leap = occurrences(date(2028, 1, 31), Frequency.MONTHLY, date(2028, 2, 29))
    assert leap == [date(2028, 1, 31), date(2028, 2, 29)]


def test_year_boundary():
    days = occurrences(date(2026, 11, 30), Frequency.MONTHLY, date(2027, 1, 31))
    assert days == [date(2026, 11, 30), date(2026, 12, 30), date(2027, 1, 30)]


def test_next_occurrence_is_strictly_after():
    assert next_occurrence(date(2026, 11, 2), Frequency.WEEKLY, date(2026, 11, 9)) == date(
        2026, 11, 16
    )
    assert next_occurrence(date(2026, 11, 2), Frequency.WEEKLY, date(2026, 11, 1)) == date(
        2026, 11, 2
    )
    assert next_occurrence(date(2026, 1, 31), Frequency.MONTHLY, date(2026, 2, 28)) == date(
        2026, 3, 31
    )


def test_the_safety_cap_limits_a_run():
    assert len(occurrences(date(2000, 1, 1), Frequency.WEEKLY, date(2026, 11, 1))) == 400
