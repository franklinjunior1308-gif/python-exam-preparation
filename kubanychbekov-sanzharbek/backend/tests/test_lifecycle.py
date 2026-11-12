import itertools

import pytest

from app.domain.enums import RequestStatus as S
from app.domain.enums import Role
from app.domain.lifecycle import (
    RULES,
    TERMINAL,
    InvalidTransition,
    ReasonRequired,
    TransitionForbidden,
    UseSchedulingFlow,
    allowed_targets,
    check_transition,
)

LISTED = {(r.source, r.target) for r in RULES}


def test_dispatcher_triages_submitted():
    rule = check_transition(S.SUBMITTED, S.TRIAGED, Role.DISPATCHER)
    assert rule.target == S.TRIAGED


def test_customer_cannot_triage():
    with pytest.raises(TransitionForbidden):
        check_transition(S.SUBMITTED, S.TRIAGED, Role.CUSTOMER, is_owner=True)


@pytest.mark.parametrize(
    ("source", "target"),
    [p for p in itertools.product(S, S) if p not in LISTED],
)
def test_every_unlisted_pair_is_rejected(source, target):
    for role in Role:
        with pytest.raises(InvalidTransition):
            check_transition(
                source, target, role, is_owner=True, is_assignee=True, reason="a valid reason"
            )


@pytest.mark.parametrize("terminal", sorted(TERMINAL))
def test_terminal_states_have_no_exits(terminal):
    for role in Role:
        assert allowed_targets(terminal, role, is_owner=True, is_assignee=True) == []


def test_customer_cancels_only_own_submitted_request():
    check_transition(S.SUBMITTED, S.CANCELED, Role.CUSTOMER, is_owner=True)
    with pytest.raises(TransitionForbidden):
        check_transition(S.SUBMITTED, S.CANCELED, Role.CUSTOMER, is_owner=False)
    # after triage only dispatcher/admin may cancel (LIFE-07)
    with pytest.raises(TransitionForbidden):
        check_transition(S.TRIAGED, S.CANCELED, Role.CUSTOMER, is_owner=True)


def test_dispatcher_cancel_needs_reason():
    with pytest.raises(ReasonRequired):
        check_transition(S.TRIAGED, S.CANCELED, Role.DISPATCHER)
    with pytest.raises(ReasonRequired):
        check_transition(S.TRIAGED, S.CANCELED, Role.DISPATCHER, reason="   ")
    check_transition(S.TRIAGED, S.CANCELED, Role.DISPATCHER, reason="duplicate")


def test_customer_closes_without_reason_but_dispatcher_needs_one():
    check_transition(S.COMPLETED, S.CLOSED, Role.CUSTOMER, is_owner=True)
    with pytest.raises(ReasonRequired):
        check_transition(S.COMPLETED, S.CLOSED, Role.ADMIN)
    check_transition(S.COMPLETED, S.CLOSED, Role.ADMIN, reason="customer unreachable")


def test_only_assigned_technician_can_accept_and_start():
    check_transition(S.SCHEDULED, S.ACCEPTED, Role.TECHNICIAN, is_assignee=True)
    with pytest.raises(TransitionForbidden):
        check_transition(S.SCHEDULED, S.ACCEPTED, Role.TECHNICIAN, is_assignee=False)
    with pytest.raises(TransitionForbidden):
        check_transition(S.ACCEPTED, S.IN_PROGRESS, Role.DISPATCHER)


def test_blocking_requires_reason_both_ways():
    with pytest.raises(ReasonRequired):
        check_transition(S.IN_PROGRESS, S.BLOCKED, Role.TECHNICIAN, is_assignee=True)
    check_transition(S.IN_PROGRESS, S.BLOCKED, Role.TECHNICIAN, is_assignee=True, reason="no part")
    with pytest.raises(ReasonRequired):
        check_transition(S.BLOCKED, S.IN_PROGRESS, Role.TECHNICIAN, is_assignee=True)


def test_reopen_flow():
    with pytest.raises(ReasonRequired):
        check_transition(S.COMPLETED, S.REOPENED, Role.CUSTOMER, is_owner=True)
    check_transition(S.COMPLETED, S.REOPENED, Role.CUSTOMER, is_owner=True, reason="still leaking")
    check_transition(S.REOPENED, S.TRIAGED, Role.DISPATCHER)


def test_scheduling_and_completion_need_dedicated_endpoints():
    with pytest.raises(UseSchedulingFlow):
        check_transition(S.TRIAGED, S.SCHEDULED, Role.DISPATCHER)
    check_transition(S.TRIAGED, S.SCHEDULED, Role.DISPATCHER, via_dedicated_endpoint=True)
    with pytest.raises(UseSchedulingFlow):
        check_transition(S.IN_PROGRESS, S.COMPLETED, Role.TECHNICIAN, is_assignee=True)


def test_allowed_targets_for_ui():
    assert allowed_targets(S.SUBMITTED, Role.DISPATCHER) == [S.TRIAGED, S.CANCELED]
    assert allowed_targets(S.SUBMITTED, Role.CUSTOMER, is_owner=True) == [S.CANCELED]
    assert allowed_targets(S.SUBMITTED, Role.CUSTOMER, is_owner=False) == []
