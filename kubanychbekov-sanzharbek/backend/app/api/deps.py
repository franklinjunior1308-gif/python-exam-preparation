from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.domain.enums import Role
from app.models import Organization, OrganizationMembership, User, UserSession

_bearer = HTTPBearer(auto_error=False)

DbDep = Annotated[Session, Depends(get_db)]


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: UserSession


@dataclass(frozen=True)
class OrgContext:
    """Every org-scoped request runs in exactly one explicitly selected organization."""

    user: User
    organization: Organization
    membership: OrganizationMembership

    @property
    def org_id(self) -> int:
        return self.organization.id

    @property
    def role(self) -> Role:
        return self.membership.role


def get_auth(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)], db: DbDep
) -> AuthContext:
    if creds is None:
        raise AppError(401, "not_authenticated", "Authentication required")
    session_id = decode_access_token(creds.credentials)
    if session_id is None:
        raise AppError(401, "invalid_token", "Invalid or expired token")

    session = db.get(UserSession, session_id)
    now = datetime.now(UTC)
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        raise AppError(401, "session_expired", "Session expired or revoked")

    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise AppError(403, "account_disabled", "Account is disabled")
    return AuthContext(user=user, session=session)


AuthDep = Annotated[AuthContext, Depends(get_auth)]


def get_org_context(
    auth: AuthDep,
    db: DbDep,
    x_organization_id: Annotated[int | None, Header()] = None,
) -> OrgContext:
    """Resolve the organization from the X-Organization-Id header and verify membership on the
    server for every request (AUTH-03). The client's choice is never trusted by itself."""
    if x_organization_id is None:
        raise AppError(400, "organization_required", "X-Organization-Id header is required")

    row = db.execute(
        select(Organization, OrganizationMembership)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .where(
            Organization.id == x_organization_id,
            OrganizationMembership.user_id == auth.user.id,
            OrganizationMembership.is_active.is_(True),
            Organization.is_active.is_(True),
        )
    ).first()
    if row is None:
        raise AppError(403, "not_a_member", "No access to this organization")
    organization, membership = row
    return OrgContext(user=auth.user, organization=organization, membership=membership)


OrgDep = Annotated[OrgContext, Depends(get_org_context)]
