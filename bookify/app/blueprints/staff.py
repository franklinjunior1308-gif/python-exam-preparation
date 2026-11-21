from datetime import timedelta

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user

from ..models import ROLE_STAFF, STATUS_CONFIRMED, Booking, utcnow
from ..services.booking_manager import BookingError, BookingManager, BookingPermissionError
from ..utils import roles_required

bp = Blueprint("staff", __name__, url_prefix="/staff")


def profile_or_403():
    if current_user.staff_profile is None:
        abort(403)
    return current_user.staff_profile


@bp.route("")
@roles_required(ROLE_STAFF)
def dashboard():
    me = profile_or_403()
    now = utcnow()
    mine = Booking.query.filter_by(staff_id=me.id)
    upcoming = (mine.filter(Booking.status == STATUS_CONFIRMED, Booking.start_time >= now - timedelta(hours=1))
                .order_by(Booking.start_time).all())
    needs_finish = (mine.filter(Booking.status == STATUS_CONFIRMED, Booking.start_time < now - timedelta(hours=1))
                    .order_by(Booking.start_time).all())
    recent = (mine.filter(Booking.status == "completed").order_by(Booking.start_time.desc()).limit(10).all())
    return render_template("staff/dashboard.html", me=me, upcoming=upcoming, needs_finish=needs_finish,
                           recent=recent, tz=me.business.timezone, now=now)


@bp.route("/bookings/<int:booking_id>/complete", methods=["POST"])
@roles_required(ROLE_STAFF)
def complete(booking_id):
    me = profile_or_403()
    booking = Booking.query.filter_by(id=booking_id, staff_id=me.id).first_or_404()
    try:
        BookingManager.complete_booking(current_user, booking)
        flash("Appointment marked as finished.", "success")
    except BookingError as e:
        flash(str(e), "error")
    except BookingPermissionError:
        abort(403)
    return redirect(url_for("staff.dashboard"))
