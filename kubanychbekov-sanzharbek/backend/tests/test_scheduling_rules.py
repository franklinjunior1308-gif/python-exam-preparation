from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.domain.scheduling import (
    available_minutes,
    earliest_slot,
    load_percent,
    missing_skills,
    overlaps,
    window_problems,
)

TZ = ZoneInfo("Asia/Bishkek")  # UTC+6, no DST
WEEKDAYS = {d: [(time(9, 0), time(18, 0))] for d in range(5)}  # Mon-Fri 09-18
NOW = datetime(2026, 11, 9, 0, 0, tzinfo=UTC)  # Monday 06:00 local


def local(day: int, hour: int, minute: int = 0) -> datetime:
    """November 2026, Bishkek local time (11/9 is a Monday)."""
    return datetime(2026, 11, day, hour, minute, tzinfo=TZ)


def check(start: datetime, end: datetime, absences=()) -> list[str]:
    return window_problems(start, end, now=NOW, tz=TZ, weekly=WEEKDAYS, absences=list(absences))


def test_touching_intervals_do_not_overlap():
    a = (local(10, 11), local(10, 12))
    b = (local(10, 12), local(10, 13))
    assert not overlaps(*a, *b)
    assert overlaps(local(10, 11), local(10, 12, 30), *b)


def test_valid_visit_has_no_problems():
    assert check(local(10, 10), local(10, 12)) == []


def test_end_must_be_after_start():
    assert check(local(10, 12), local(10, 12)) == ["invalid_range"]
    assert check(local(10, 12), local(10, 11)) == ["invalid_range"]


def test_minimum_duration_is_thirty_minutes():
    assert "too_short" in check(local(10, 10), local(10, 10, 20))
    assert check(local(10, 10), local(10, 10, 30)) == []


def test_visit_cannot_start_in_the_past():
    assert "in_past" in check(local(9, 5), local(9, 6))


def test_outside_working_hours_and_weekends_are_rejected():
    assert "outside_availability" in check(local(10, 8), local(10, 10))
    assert "outside_availability" in check(local(10, 17), local(10, 19))
    assert "outside_availability" in check(local(14, 10), local(14, 12))  # Saturday


def test_visit_crossing_midnight_is_rejected():
    assert "outside_availability" in check(local(10, 17), local(11, 10))


def test_absence_blocks_the_visit():
    absence = (local(10, 0), local(12, 0))
    assert "absent" in check(local(11, 10), local(11, 11), [absence])
    assert check(local(12, 10), local(12, 11), [absence]) == []


def test_timezone_conversion_uses_the_organization_zone():
    start_utc = datetime(2026, 11, 10, 4, 0, tzinfo=UTC)  # 10:00 in Bishkek
    assert check(start_utc, start_utc + timedelta(hours=2)) == []
    early_utc = datetime(2026, 11, 10, 1, 0, tzinfo=UTC)  # 07:00 in Bishkek
    assert "outside_availability" in check(early_utc, early_utc + timedelta(hours=1))


def test_all_category_skills_are_required():
    assert missing_skills(["HVAC", "Electrical"], ["hvac"]) == ["Electrical"]
    assert missing_skills(["HVAC"], [" hvac "]) == []
    assert missing_skills([], []) == []


def test_available_minutes_for_a_work_week():
    minutes = available_minutes(local(9, 0), local(16, 0), tz=TZ, weekly=WEEKDAYS, absences=[])
    assert minutes == 5 * 9 * 60


def test_absence_reduces_available_minutes():
    absence = (local(10, 0), local(11, 0))  # all of Tuesday
    minutes = available_minutes(
        local(9, 0), local(16, 0), tz=TZ, weekly=WEEKDAYS, absences=[absence]
    )
    assert minutes == 4 * 9 * 60


def slot(
    *,
    not_before: datetime | None = None,
    weekly: dict[int, list[tuple[time, time]]] | None = None,
    absences: list[tuple[datetime, datetime]] | None = None,
    busy: list[tuple[datetime, datetime]] | None = None,
    must_end_by: datetime | None = None,
    horizon_days: int = 14,
):
    return earliest_slot(
        duration=timedelta(hours=2),
        not_before=not_before or local(10, 8),  # Tuesday 08:00
        horizon_days=horizon_days,
        tz=TZ,
        weekly=WEEKDAYS if weekly is None else weekly,
        absences=absences or [],
        busy=busy or [],
        must_end_by=must_end_by,
    )


def as_local(result):
    return tuple(moment.astimezone(TZ) for moment in result)


def test_earliest_slot_starts_when_the_workday_opens():
    start, end = as_local(slot())
    assert (start, end) == (local(10, 9), local(10, 11))


def test_earliest_slot_skips_busy_time_and_uses_the_next_gap():
    busy = [(local(10, 9).astimezone(UTC), local(10, 12).astimezone(UTC))]
    start, _ = as_local(slot(busy=busy))
    assert start == local(10, 12)  # touching the end of the busy block is fine


def test_earliest_slot_rounds_up_to_the_half_hour_grid():
    start, _ = as_local(slot(not_before=local(10, 9, 7)))
    assert start == local(10, 9, 30)


def test_earliest_slot_moves_to_next_workday_when_today_is_full():
    start, _ = as_local(slot(not_before=local(10, 17)))  # 2h does not fit before 18:00
    assert start == local(11, 9)


def test_earliest_slot_skips_weekends_and_absences():
    friday_evening = local(13, 17)
    start, _ = as_local(slot(not_before=friday_evening))
    assert start == local(16, 9)  # next Monday
    absence = [(local(10, 0).astimezone(UTC), local(12, 0).astimezone(UTC))]
    start, _ = as_local(slot(absences=absence))
    assert start == local(12, 9)


def test_earliest_slot_respects_the_deadline_and_horizon():
    assert slot(must_end_by=local(10, 10)) is None
    assert slot(weekly={}, horizon_days=3) is None


def test_load_percent_is_capped_and_safe():
    assert load_percent(270, 540) == 50
    assert load_percent(900, 540) == 100
    assert load_percent(100, 0) == 0
