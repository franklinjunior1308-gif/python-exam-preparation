"""scheduling

Revision ID: 8ce0d23ec3d9
Revises: 00a4004d4492
Create Date: 2026-11-12 15:16:05.752620
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "8ce0d23ec3d9"
down_revision: str | None = "00a4004d4492"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # needed so the exclusion constraint can combine `technician_id =` with a range overlap
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    # must exist before `assignments` can reference (organization_id, id) of requests
    op.create_unique_constraint(
        "uq_service_requests_organization_id_id", "service_requests", ["organization_id", "id"]
    )
    op.create_table(
        "technician_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id"),
        sa.UniqueConstraint("organization_id", "user_id"),
    )
    op.create_index(
        op.f("ix_technician_profiles_organization_id"),
        "technician_profiles",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_technician_profiles_user_id"), "technician_profiles", ["user_id"], unique=False
    )
    op.create_table(
        "technician_absences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("technician_id", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.CheckConstraint("end_at > start_at", name="ck_absence_order"),
        sa.ForeignKeyConstraint(
            ["organization_id", "technician_id"],
            ["technician_profiles.organization_id", "technician_profiles.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_absence_tech", "technician_absences", ["technician_id", "start_at"], unique=False
    )
    op.create_table(
        "technician_availability",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("technician_id", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.CheckConstraint("end_time > start_time", name="ck_availability_order"),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_availability_weekday"),
        sa.ForeignKeyConstraint(
            ["organization_id", "technician_id"],
            ["technician_profiles.organization_id", "technician_profiles.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_availability_tech",
        "technician_availability",
        ["technician_id", "weekday"],
        unique=False,
    )
    op.create_table(
        "technician_skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("technician_id", sa.Integer(), nullable=False),
        sa.Column("skill", sa.String(length=60), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "technician_id"],
            ["technician_profiles.organization_id", "technician_profiles.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "technician_id", "skill"),
    )
    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("technician_id", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "SCHEDULED",
                "ACCEPTED",
                "IN_PROGRESS",
                "BLOCKED",
                "COMPLETED",
                "CANCELED",
                "DECLINED",
                name="assignmentstatus",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        postgresql.ExcludeConstraint(
            (sa.column("technician_id"), "="),
            (sa.literal_column("tstzrange(start_at, end_at, '[)')"), "&&"),
            where=sa.text("status IN ('SCHEDULED', 'ACCEPTED', 'IN_PROGRESS', 'BLOCKED')"),
            using="gist",
            name="ex_assignment_no_overlap",
        ),
        sa.CheckConstraint(
            "end_at >= start_at + interval '30 minutes'", name="ck_assignment_min_duration"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "request_id"],
            ["service_requests.organization_id", "service_requests.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "technician_id"],
            ["technician_profiles.organization_id", "technician_profiles.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assignment_org_start", "assignments", ["organization_id", "start_at"], unique=False
    )
    op.create_index(
        "ix_assignment_tech_start", "assignments", ["technician_id", "start_at"], unique=False
    )
    op.create_index(
        "uq_assignment_one_active_per_request",
        "assignments",
        ["request_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('SCHEDULED', 'ACCEPTED', 'IN_PROGRESS', 'BLOCKED')"),
    )
    op.add_column(
        "service_categories",
        sa.Column(
            "required_skills",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_constraint("uq_service_requests_organization_id_id", "service_requests", type_="unique")
    op.drop_column("service_categories", "required_skills")
    op.drop_index(
        "uq_assignment_one_active_per_request",
        table_name="assignments",
        postgresql_where=sa.text("status IN ('SCHEDULED', 'ACCEPTED', 'IN_PROGRESS', 'BLOCKED')"),
    )
    op.drop_index("ix_assignment_tech_start", table_name="assignments")
    op.drop_index("ix_assignment_org_start", table_name="assignments")
    op.drop_table("assignments")
    op.drop_table("technician_skills")
    op.drop_index("ix_availability_tech", table_name="technician_availability")
    op.drop_table("technician_availability")
    op.drop_index("ix_absence_tech", table_name="technician_absences")
    op.drop_table("technician_absences")
    op.drop_index(op.f("ix_technician_profiles_user_id"), table_name="technician_profiles")
    op.drop_index(op.f("ix_technician_profiles_organization_id"), table_name="technician_profiles")
    op.drop_table("technician_profiles")
