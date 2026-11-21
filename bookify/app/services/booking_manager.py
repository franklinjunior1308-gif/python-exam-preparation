from datetime import timedelta

from flask import current_app
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from ..extensions import db
from ..models import (STATUS_CANCELLED, STATUS_COMPLETED, STATUS_CONFIRMED, Booking, Service,
                      StaffMember, utcnow)
from .availability import AvailabilityService
from .notifications import NotificationService


class BookingError(Exception):
    """A rule violation the user can understand (shown as a flash message)."""


class BookingPermissionError(Exception):
    """The acting user may not touch this booking."""


class BookingManager:
    """Creates, cancels and completes bookings, enforcing every business rule server-side."""

    @staticmethod
    def _begin_exclusive(staff_id):
        """Serialise writers so two requests cannot both see a slot as free.

        SQLite: ``BEGIN IMMEDIATE`` takes the database write lock *before* we read
        existing bookings, so the check-then-insert below is atomic across processes
        and threads (others wait up to the busy timeout). Other databases: lock the
        staff row with SELECT ... FOR UPDATE.
        A partial unique index on (staff_id, start_time) is a final DB-level guard.
        """
        if db.engine.dialect.name == "sqlite":
            raw = db.session.connection().connection.dbapi_connection
            if getattr(raw, "in_transaction", False):
                db.session.commit()
            db.session.execute(text("BEGIN IMMEDIATE"))
        else:
            db.session.query(StaffMember).filter_by(id=staff_id).with_for_update().first()

    @classmethod
    def create_booking(cls, customer, business, service_id, staff_id, start_utc, notes="", now=None):
        now = now or utcnow()
        cfg = current_app.config
        if start_utc is None:
            raise BookingError("Please choose a valid appointment time.")
        if start_utc <= now:
            raise BookingError("Appointments must be in the future.")
        if start_utc > now + timedelta(days=cfg["BOOKING_HORIZON_DAYS"]):
            raise BookingError("That date is too far ahead to book.")

        customer_id = customer.id
        service = Service.query.filter_by(id=service_id, business_id=business.id).first()
        if service is None or not service.is_active:
            raise BookingError("That service is not available.")

        candidates = ([staff_id] if staff_id else
                      [s.id for s in AvailabilityService.qualified_staff(business, service)])
        if not candidates:
            raise BookingError("No staff member offers this service.")
        if staff_id:
            staff = StaffMember.query.filter_by(id=staff_id, business_id=business.id).first()
            if staff is None or not staff.is_active or service not in staff.services:
                raise BookingError("That staff member is not qualified for this service.")

        try:
            cls._begin_exclusive(candidates[0])
            booking = None
            for sid in candidates:
                staff = db.session.get(StaffMember, sid)
                if AvailabilityService.is_slot_available(business, staff, service, start_utc, now):
                    booking = Booking(
                        business_id=business.id, customer_id=customer_id, service_id=service.id,
                        staff_id=sid, start_time=start_utc,
                        end_time=start_utc + timedelta(minutes=service.duration_minutes),
                        status=STATUS_CONFIRMED, price_cents=service.price_cents,
                        duration_minutes=service.duration_minutes, notes=(notes or "")[:500],
                    )
                    db.session.add(booking)
                    db.session.flush()
                    break
            if booking is None:
                db.session.rollback()
                raise BookingError("Sorry, that time slot is no longer available.")
            NotificationService.booking_created(booking)
            db.session.commit()
            return booking
        except (IntegrityError, OperationalError):
            db.session.rollback()
            raise BookingError("Sorry, that time slot is no longer available. Please pick another.")

    @staticmethod
    def can_customer_cancel(booking, now=None):
        now = now or utcnow()
        cutoff = timedelta(hours=current_app.config["CUSTOMER_CANCEL_CUTOFF_HOURS"])
        return booking.status == STATUS_CONFIRMED and booking.start_time - now >= cutoff

    @classmethod
    def cancel_booking(cls, user, booking, now=None):
        now = now or utcnow()
        is_owner_admin = user.is_admin and booking.business.owner_id == user.id
        if not (is_owner_admin or (user.is_customer and booking.customer_id == user.id)):
            raise BookingPermissionError("You cannot modify this booking.")
        if booking.status == STATUS_COMPLETED:
            raise BookingError("Completed appointments cannot be cancelled.")
        if booking.status == STATUS_CANCELLED:
            raise BookingError("This booking is already cancelled.")
        if not is_owner_admin and not cls.can_customer_cancel(booking, now):
            hours = current_app.config["CUSTOMER_CANCEL_CUTOFF_HOURS"]
            raise BookingError(f"Bookings can only be cancelled at least {hours} hours in advance. "
                               "Please contact the business.")
        booking.status = STATUS_CANCELLED
        booking.cancelled_at = now
        booking.cancelled_by_id = user.id
        NotificationService.booking_cancelled(booking, user)
        db.session.commit()
        return booking

    @classmethod
    def complete_booking(cls, user, booking, now=None):
        now = now or utcnow()
        allowed = ((user.is_staff_member and user.staff_profile and booking.staff_id == user.staff_profile.id)
                   or (user.is_admin and booking.business.owner_id == user.id))
        if not allowed:
            raise BookingPermissionError("You cannot modify this booking.")
        if booking.status != STATUS_CONFIRMED:
            raise BookingError("Only confirmed appointments can be marked as finished.")
        if booking.start_time > now:
            raise BookingError("You can only finish an appointment once it has started.")
        booking.status = STATUS_COMPLETED
        NotificationService.booking_completed(booking)
        db.session.commit()
        return booking
