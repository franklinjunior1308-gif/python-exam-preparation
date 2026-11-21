"""SQLAlchemy models.

All datetimes are stored as naive UTC. Use app.utils helpers to convert to the
business time zone for display.
"""
from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager

ROLE_ADMIN = "admin"
ROLE_STAFF = "staff"
ROLE_CUSTOMER = "customer"

STATUS_CONFIRMED = "confirmed"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40))
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_CUSTOMER, index=True)
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        CheckConstraint("role in ('admin','staff','customer')", name="ck_users_role"),
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):  # Flask-Login
        return self.is_active_account

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    @property
    def is_staff_member(self):
        return self.role == ROLE_STAFF

    @property
    def is_customer(self):
        return self.role == ROLE_CUSTOMER

    def __repr__(self):
        return f"<User {self.email} {self.role}>"


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


class Business(db.Model):
    __tablename__ = "businesses"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), nullable=False, unique=True, index=True)
    category = db.Column(db.String(60), default="Other")
    description = db.Column(db.Text, default="")
    address = db.Column(db.String(200), default="")
    phone = db.Column(db.String(40), default="")
    timezone = db.Column(db.String(64), nullable=False, default="UTC")
    slot_interval_minutes = db.Column(db.Integer, nullable=False, default=30)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    owner = db.relationship("User", backref=db.backref("business", uselist=False))
    services = db.relationship("Service", backref="business", cascade="all, delete-orphan")
    staff_members = db.relationship("StaffMember", backref="business", cascade="all, delete-orphan")


staff_services = db.Table(
    "staff_services",
    db.Column("staff_id", db.Integer, db.ForeignKey("staff_members.id"), primary_key=True),
    db.Column("service_id", db.Integer, db.ForeignKey("services.id"), primary_key=True),
)


class Service(db.Model):
    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    price_cents = db.Column(db.Integer, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="ck_services_price"),
        CheckConstraint("duration_minutes > 0", name="ck_services_duration"),
    )

    @property
    def price(self):
        return self.price_cents / 100


class StaffMember(db.Model):
    __tablename__ = "staff_members"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    title = db.Column(db.String(80), default="")
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    user = db.relationship("User", backref=db.backref("staff_profile", uselist=False))
    services = db.relationship("Service", secondary=staff_services, backref="staff_members")
    schedules = db.relationship(
        "WorkSchedule", backref="staff", cascade="all, delete-orphan", order_by="WorkSchedule.weekday"
    )

    @property
    def name(self):
        return self.user.name


class WorkSchedule(db.Model):
    """One working block per staff member per weekday (0 = Monday), in business local time."""

    __tablename__ = "work_schedules"

    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff_members.id"), nullable=False)
    weekday = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    __table_args__ = (
        UniqueConstraint("staff_id", "weekday", name="uq_schedule_staff_weekday"),
        CheckConstraint("weekday between 0 and 6", name="ck_schedule_weekday"),
        CheckConstraint("end_time > start_time", name="ck_schedule_times"),
    )


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff_members.id"), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)  # UTC
    end_time = db.Column(db.DateTime, nullable=False)  # UTC
    status = db.Column(db.String(20), nullable=False, default=STATUS_CONFIRMED)
    price_cents = db.Column(db.Integer, nullable=False)  # snapshot at creation
    duration_minutes = db.Column(db.Integer, nullable=False)  # snapshot at creation
    notes = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    cancelled_at = db.Column(db.DateTime)
    cancelled_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    business = db.relationship("Business")
    customer = db.relationship("User", foreign_keys=[customer_id], backref="bookings")
    service = db.relationship("Service")
    staff = db.relationship("StaffMember", backref="bookings")

    __table_args__ = (
        CheckConstraint("status in ('confirmed','completed','cancelled')", name="ck_bookings_status"),
        CheckConstraint("end_time > start_time", name="ck_bookings_times"),
        Index("ix_bookings_staff_start", "staff_id", "start_time"),
        # Secondary DB-level guard: one active booking per staff member per start instant.
        Index(
            "uq_bookings_active_slot",
            "staff_id",
            "start_time",
            unique=True,
            sqlite_where=db.text("status != 'cancelled'"),
        ),
    )

    @property
    def is_active(self):
        return self.status != STATUS_CANCELLED


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    message = db.Column(db.String(300), nullable=False)
    link = db.Column(db.String(200))
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User", backref="notifications")
