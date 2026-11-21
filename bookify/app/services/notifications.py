from ..extensions import db
from ..models import Notification
from ..utils import to_local


class NotificationService:
    """Internal (in-app) notifications. No email/SMS in the MVP."""

    @staticmethod
    def notify(user_id, message, link=None):
        """Add a notification to the current session (caller commits)."""
        n = Notification(user_id=user_id, message=message[:300], link=link)
        db.session.add(n)
        return n

    @staticmethod
    def _when(booking):
        local = to_local(booking.start_time, booking.business.timezone)
        return local.strftime("%a %d %b, %H:%M")

    @classmethod
    def booking_created(cls, booking):
        when = cls._when(booking)
        cls.notify(booking.customer_id, f"Your booking for {booking.service.name} on {when} is confirmed.",
                   f"/bookings/{booking.id}/confirmation")
        cls.notify(booking.staff.user_id, f"New booking: {booking.service.name} with {booking.customer.name} on {when}.",
                   "/staff")
        cls.notify(booking.business.owner_id, f"New booking: {booking.service.name} with {booking.staff.name} on {when}.",
                   "/admin/calendar")

    @classmethod
    def booking_cancelled(cls, booking, cancelled_by):
        when = cls._when(booking)
        msg = f"Booking for {booking.service.name} on {when} was cancelled."
        recipients = {booking.customer_id, booking.staff.user_id, booking.business.owner_id}
        recipients.discard(cancelled_by.id)
        for uid in recipients:
            cls.notify(uid, msg)

    @classmethod
    def booking_completed(cls, booking):
        cls.notify(booking.customer_id,
                   f"Your {booking.service.name} appointment is complete. Thanks for visiting {booking.business.name}!",
                   "/bookings")

    @staticmethod
    def unread_count(user_id):
        return Notification.query.filter_by(user_id=user_id, is_read=False).count()

    @staticmethod
    def for_user(user_id, limit=100):
        return (Notification.query.filter_by(user_id=user_id)
                .order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit).all())

    @staticmethod
    def mark_read(user_id, notification_id):
        n = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        if n:
            n.is_read = True
            db.session.commit()
        return n

    @staticmethod
    def mark_all_read(user_id):
        Notification.query.filter_by(user_id=user_id, is_read=False).update({"is_read": True})
        db.session.commit()
