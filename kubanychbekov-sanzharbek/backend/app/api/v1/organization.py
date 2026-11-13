from fastapi import APIRouter

from app.api.deps import DbDep, OrgDep
from app.core.errors import AppError
from app.domain.enums import Role
from app.schemas.organization import OrganizationOut, OrganizationUpdate
from app.services.audit import record_audit

router = APIRouter(tags=["organization"])


@router.get("/settings/organization", response_model=OrganizationOut)
def get_organization(ctx: OrgDep) -> OrganizationOut:
    return OrganizationOut(
        id=ctx.org_id, name=ctx.organization.name, timezone=ctx.organization.timezone
    )


@router.put("/settings/organization", response_model=OrganizationOut)
def update_organization(data: OrganizationUpdate, ctx: OrgDep, db: DbDep) -> OrganizationOut:
    """Name and IANA time zone of the organization (ORG-01). Administrators only.

    Instants stay stored in UTC, so a new time zone changes how times are shown and how working
    hours and SLA days are counted from now on, never the stored data.
    """
    if ctx.role != Role.ADMIN:
        raise AppError(403, "forbidden", "Only administrators change organization settings")
    org = ctx.organization
    before = {"name": org.name, "timezone": org.timezone}
    org.name = data.name
    org.timezone = data.timezone
    record_audit(
        db,
        action="organization.updated",
        object_type="organization",
        object_id=org.id,
        organization_id=org.id,
        actor_user_id=ctx.user.id,
        before=before,
        after={"name": org.name, "timezone": org.timezone},
    )
    db.commit()
    return OrganizationOut(id=org.id, name=org.name, timezone=org.timezone)
