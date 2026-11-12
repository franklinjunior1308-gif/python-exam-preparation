"""Administrator edits of a technician's skills and weekly availability (ORG-01)."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import OrgContext
from app.core.errors import AppError
from app.domain.enums import Role
from app.models import TechnicianAvailability, TechnicianProfile, TechnicianSkill
from app.schemas.scheduling import TechnicianOut, TechnicianProfileIn
from app.services.audit import record_audit
from app.services.scheduling import technician_list


def update_profile(
    db: Session, ctx: OrgContext, technician_id: int, data: TechnicianProfileIn
) -> TechnicianOut:
    if ctx.role != Role.ADMIN:
        raise AppError(403, "forbidden", "Only administrators edit technician profiles")
    profile = db.scalar(
        select(TechnicianProfile)
        .where(
            TechnicianProfile.id == technician_id,
            TechnicianProfile.organization_id == ctx.org_id,
        )
        .with_for_update()
    )
    if profile is None:
        raise AppError(404, "technician_not_found", "Technician not found")

    before = technician_list_entry(db, ctx, technician_id)
    db.execute(delete(TechnicianSkill).where(TechnicianSkill.technician_id == profile.id))
    db.execute(
        delete(TechnicianAvailability).where(TechnicianAvailability.technician_id == profile.id)
    )
    for skill in data.skills:
        db.add(TechnicianSkill(organization_id=ctx.org_id, technician_id=profile.id, skill=skill))
    for span in data.availability:
        db.add(
            TechnicianAvailability(
                organization_id=ctx.org_id,
                technician_id=profile.id,
                weekday=span.weekday,
                start_time=span.start_time,
                end_time=span.end_time,
            )
        )
    if data.is_active is not None:
        profile.is_active = data.is_active
    db.flush()
    after = technician_list_entry(db, ctx, technician_id)
    record_audit(
        db,
        action="technician.profile_updated",
        object_type="technician",
        object_id=profile.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        before={"skills": before.skills, "is_active": before.is_active},
        after={"skills": after.skills, "is_active": after.is_active},
    )
    db.commit()
    return after


def technician_list_entry(db: Session, ctx: OrgContext, technician_id: int) -> TechnicianOut:
    for row in technician_list(db, ctx):
        if row.id == technician_id:
            return row
    raise AppError(404, "technician_not_found", "Technician not found")
