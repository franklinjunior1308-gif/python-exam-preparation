from datetime import datetime, timedelta

from ..models import STATUS_CANCELLED, Booking, StaffMember, utcnow
from ..utils import local_to_utc, to_local


class AvailabilityService:
    """Pure scheduling logic: which start times can a service be booked at?"""

    @staticmethod
    def qualified_staff(business, service):
        return [s for s in business.staff_members
                if s.is_active and service in s.services]

    @staticmethod
    def _overlapping(staff_id, start, end):
        return (Booking.query.filter(
            Booking.staff_id == staff_id,
            Booking.status != STATUS_CANCELLED,
            Booking.start_time < end,
            Booking.end_time > start,
        ))

    @classmethod
    def staff_slots(cls, business, staff, service, local_date, now=None):
        """Available start times (naive UTC) for one staff member on a local date."""
        now = now or utcnow()
        if not staff.is_active or service not in staff.services or not service.is_active:
            return []
        block = next((w for w in staff.schedules if w.weekday == local_date.weekday()), None)
        if block is None:
            return []
        interval = timedelta(minutes=business.slot_interval_minutes)
        duration = timedelta(minutes=service.duration_minutes)

        day_start = local_to_utc(local_date, block.start_time, business.timezone)
        day_end = local_to_utc(local_date, block.end_time, business.timezone)

        booked = Booking.query.filter(
            Booking.staff_id == staff.id,
            Booking.status != STATUS_CANCELLED,
            Booking.start_time < day_end,
            Booking.end_time > day_start,
        ).all()

        slots = []
        t = day_start
        while t + duration <= day_end:
            end = t + duration
            if t > now and not any(b.start_time < end and b.end_time > t for b in booked):
                slots.append(t)
            t += interval
        return slots

    @classmethod
    def get_slots(cls, business, service, local_date, staff=None, now=None):
        """Return [{'start': datetime, 'staff_ids': [...]}] sorted by start.

        If ``staff`` is None, slots from every qualified staff member are merged.
        """
        staff_list = [staff] if staff else cls.qualified_staff(business, service)
        merged = {}
        for s in staff_list:
            for start in cls.staff_slots(business, s, service, local_date, now):
                merged.setdefault(start, []).append(s.id)
        return [{"start": k, "staff_ids": v} for k, v in sorted(merged.items())]

    @classmethod
    def is_slot_available(cls, business, staff, service, start_utc, now=None):
        local_date = to_local(start_utc, business.timezone).date()
        return start_utc in cls.staff_slots(business, staff, service, local_date, now)
