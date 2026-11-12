"""Service request lifecycle (LIFE-01 .. LIFE-07) as a pure, database-free state machine.

The API layer calls `check_transition` before touching the database, then performs the
state change with a conditional UPDATE so concurrent requests cannot both succeed.
"""

from dataclasses import dataclass

from app.domain.enums import RequestStatus as S
from app.domain.enums import Role


class TransitionError(Exception):
    """Base class; `code` is the machine-readable error code returned by the API."""

    code = "transition_error"


class InvalidTransition(TransitionError):
    code = "invalid_transition"


class TransitionForbidden(TransitionError):
    code = "transition_forbidden"


class ReasonRequired(TransitionError):
    code = "reason_required"


class UseSchedulingFlow(TransitionError):
    """Allowed in principle, but must go through its dedicated endpoint (assignment, completion)."""

    code = "requires_dedicated_endpoint"


@dataclass(frozen=True)
class Rule:
    source: S
    target: S
    roles: frozenset[Role]
    owner_only: bool = False  # the customer must be the author of the request
    assignee_only: bool = False  # the technician must be assigned to the request
    reason_required: bool = False
    dedicated_endpoint: bool = False  # needs side effects (assignment, evidence, ...)


_DISPATCH = frozenset({Role.DISPATCHER, Role.ADMIN})
_CUSTOMER = frozenset({Role.CUSTOMER})
_TECH = frozenset({Role.TECHNICIAN})

RULES: tuple[Rule, ...] = (
    Rule(S.SUBMITTED, S.TRIAGED, _DISPATCH),
    Rule(S.TRIAGED, S.SCHEDULED, _DISPATCH, dedicated_endpoint=True),
    Rule(S.SCHEDULED, S.ACCEPTED, _TECH, assignee_only=True),
    Rule(S.ACCEPTED, S.IN_PROGRESS, _TECH, assignee_only=True),
    Rule(S.IN_PROGRESS, S.COMPLETED, _TECH, assignee_only=True, dedicated_endpoint=True),
    Rule(S.COMPLETED, S.CLOSED, _CUSTOMER, owner_only=True),
    Rule(S.COMPLETED, S.CLOSED, _DISPATCH, reason_required=True),
    # cancellation
    Rule(S.SUBMITTED, S.CANCELED, _CUSTOMER, owner_only=True),
    Rule(S.SUBMITTED, S.CANCELED, _DISPATCH, reason_required=True),
    Rule(S.TRIAGED, S.CANCELED, _DISPATCH, reason_required=True),
    Rule(S.SCHEDULED, S.CANCELED, _DISPATCH, reason_required=True, dedicated_endpoint=True),
    # technician declines / dispatcher unassigns before work starts
    Rule(S.SCHEDULED, S.TRIAGED, _TECH, assignee_only=True, dedicated_endpoint=True),
    Rule(S.ACCEPTED, S.TRIAGED, _TECH, assignee_only=True, dedicated_endpoint=True),
    Rule(S.SCHEDULED, S.TRIAGED, _DISPATCH, dedicated_endpoint=True),
    Rule(S.ACCEPTED, S.TRIAGED, _DISPATCH, dedicated_endpoint=True),
    # blocking
    Rule(S.IN_PROGRESS, S.BLOCKED, _TECH, assignee_only=True, reason_required=True),
    Rule(S.BLOCKED, S.IN_PROGRESS, _TECH, assignee_only=True, reason_required=True),
    # rework
    Rule(S.COMPLETED, S.REOPENED, _CUSTOMER, owner_only=True, reason_required=True),
    Rule(S.REOPENED, S.TRIAGED, _DISPATCH),
)

TERMINAL = frozenset({S.CLOSED, S.CANCELED})


def _applies(rule: Rule, role: Role, is_owner: bool, is_assignee: bool) -> bool:
    if role not in rule.roles:
        return False
    if rule.owner_only and not is_owner:
        return False
    return not (rule.assignee_only and not is_assignee)


def check_transition(
    source: S,
    target: S,
    role: Role,
    *,
    is_owner: bool = False,
    is_assignee: bool = False,
    reason: str | None = None,
    via_dedicated_endpoint: bool = False,
) -> Rule:
    """Return the matching rule or raise a TransitionError subclass."""
    candidates = [r for r in RULES if r.source == source and r.target == target]
    if not candidates:
        raise InvalidTransition(f"{source} -> {target} is not allowed")

    allowed = [r for r in candidates if _applies(r, role, is_owner, is_assignee)]
    if not allowed:
        raise TransitionForbidden(f"role '{role}' may not perform {source} -> {target} here")

    rule = allowed[0]
    if rule.dedicated_endpoint and not via_dedicated_endpoint:
        raise UseSchedulingFlow(f"{source} -> {target} must use its dedicated endpoint")
    if rule.reason_required and not (reason and reason.strip()):
        raise ReasonRequired(f"a reason is required for {source} -> {target}")
    return rule


def allowed_targets(
    source: S,
    role: Role,
    *,
    is_owner: bool = False,
    is_assignee: bool = False,
    include_dedicated: bool = False,
) -> list[S]:
    """Targets the actor could pick right now (used for the 'allowed actions' in the UI).

    Transitions that need a dedicated endpoint (assignment, completion) are left out unless
    `include_dedicated` is set, because the generic transition endpoint rejects them.
    """
    result: list[S] = []
    for rule in RULES:
        if rule.dedicated_endpoint and not include_dedicated:
            continue
        if rule.source == source and _applies(rule, role, is_owner, is_assignee):
            if rule.target not in result:
                result.append(rule.target)
    return result
