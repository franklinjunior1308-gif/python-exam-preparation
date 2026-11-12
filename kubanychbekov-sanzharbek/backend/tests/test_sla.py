from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.domain.enums import Priority
from app.domain.sla import (
    DEFAULT_WEEKLY,
    budget_minutes,
    deadline,
    remaining_after_priority_change,
    sla_state,
    working_minutes,
)

TZ = ZoneInfo("Asia/Bishkek")  # UTC+6


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """November 2026 in Bishkek time (11/13 is a Friday, 11/16 a Monday)."""
    return datetime(2026, 11, day, hour, minute, tzinfo=TZ).astimezone(UTC)


def local(moment: datetime) -> datetime:
    return moment.astimezone(TZ)


def work(start, end, holidays=frozenset(), pauses=()):
    return working_minutes(
        start, end, tz=TZ, weekly=DEFAULT_WEEKLY, holidays=holidays, pauses=pauses
    )


def due(start, minutes, holidays=frozenset(), pauses=()):
    return deadline(start, minutes, tz=TZ, weekly=DEFAULT_WEEKLY, holidays=holidays, pauses=pauses)


def test_default_budgets_follow_the_priority():
    assert budget_minutes(Priority.HIGH) == 8 * 60
    assert budget_minutes(Priority.NORMAL) == 24 * 60
    assert budget_minutes(Priority.LOW) == 48 * 60


def test_only_working_hours_count():
    assert work(at(12, 9), at(12, 18)) == 9 * 60  # a full Thursday
    assert work(at(12, 6), at(12, 20)) == 9 * 60  # night hours do not count
    assert work(at(12, 12), at(12, 12)) == 0


def test_weekend_is_skipped_so_a_friday_evening_high_request_ends_on_monday():
    # created Friday 17:00: one hour left on Friday, seven more on Monday (SLA-02, E2E-07)
    end = due(at(13, 17), 8 * 60)
    assert local(end) == local(at(16, 16))
    assert work(at(13, 17), at(16, 16)) == 8 * 60


def test_a_holiday_moves_the_deadline_by_a_whole_working_day():
    monday = frozenset({date(2026, 11, 16)})
    end = due(at(13, 17), 8 * 60, holidays=monday)
    assert local(end) == local(at(17, 16))  # Tuesday 16:00
    assert work(at(13, 17), at(17, 16), holidays=monday) == 8 * 60


def test_time_with_the_customer_is_paused_and_the_rest_keeps_counting():
    # an estimate waits from Friday 17:30 to Monday 10:00 (SLA-03)
    pauses = [(at(13, 17, 30), at(16, 10))]
    assert (
        work(at(13, 17), at(16, 12), pauses=pauses) == 30 + 2 * 60
    )  # 17:00-17:30, then 10:00-12:00
    end = due(at(13, 17), 8 * 60, pauses=pauses)
    assert local(end) == local(at(16, 17, 30))  # 30 min + 7.5 h after the pause ends


def test_overlapping_pauses_are_merged_not_subtracted_twice():
    pauses = [(at(12, 10), at(12, 12)), (at(12, 11), at(12, 13))]
    assert work(at(12, 9), at(12, 18), pauses=pauses) == 9 * 60 - 3 * 60


def test_states_at_risk_and_overdue_thresholds():
    budget = 8 * 60
    assert sla_state(budget, 0) == ("ON_TRACK", 480)
    assert sla_state(budget, 359) == ("ON_TRACK", 121)
    assert sla_state(budget, 360) == ("AT_RISK", 120)  # exactly 25% left
    assert sla_state(budget, 480) == ("AT_RISK", 0)
    assert sla_state(budget, 481) == ("OVERDUE", -1)


def test_changing_the_priority_recomputes_from_the_used_time():
    used = 10 * 60  # ten working hours already spent
    assert remaining_after_priority_change(budget_minutes(Priority.LOW), used)[0] == "ON_TRACK"
    state, remaining = remaining_after_priority_change(budget_minutes(Priority.HIGH), used)
    assert (state, remaining) == ("OVERDUE", -120)


def test_no_working_hours_means_no_deadline():
    assert deadline(at(12, 9), 60, tz=TZ, weekly={}, holidays=frozenset()) is None
