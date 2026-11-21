from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import ROLE_CUSTOMER, STATUS_CANCELLED, STATUS_CONFIRMED, Booking, utcnow
from ..services.booking_manager import BookingError, BookingManager, BookingPermissionError
from ..services.notifications import NotificationService
from ..utils import roles_required

bp = Blueprint("customer", __name__)


def own_booking_or_404(booking_id):
    """Customers only ever see their own bookings; anything else is a 404."""
    return Booking.query.filter_by(id=booking_id, customer_id=current_user.id).first_or_404()


@bp.route("/dashboard")
@roles_required(ROLE_CUSTOMER)
def dashboard():
    now = utcnow()
    upcoming = (Booking.query.filter(Booking.customer_id == current_user.id,
                                     Booking.status == STATUS_CONFIRMED, Booking.start_time >= now)
                .order_by(Booking.start_time).all())
    total = Booking.query.filter_by(customer_id=current_user.id).count()
    return render_template("customer/dashboard.html", upcoming=upcoming, total=total,
                           can_cancel=BookingManager.can_customer_cancel)


@bp.route("/bookings")
@roles_required(ROLE_CUSTOMER)
def history():
    status = request.args.get("status", "")
    q = Booking.query.filter_by(customer_id=current_user.id)
    if status in ("confirmed", "completed", "cancelled"):
        q = q.filter_by(status=status)
    bookings = q.order_by(Booking.start_time.desc()).all()
    return render_template("customer/history.html", bookings=bookings, status=status,
                           can_cancel=BookingManager.can_customer_cancel)


@bp.route("/bookings/<int:booking_id>/confirmation")
@roles_required(ROLE_CUSTOMER)
def confirmation(booking_id):
    return render_template("customer/confirmation.html", booking=own_booking_or_404(booking_id))


@bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@roles_required(ROLE_CUSTOMER)
def cancel(booking_id):
    booking = own_booking_or_404(booking_id)
    try:
        BookingManager.cancel_booking(current_user, booking)
        flash("Your booking was cancelled.", "success")
    except BookingError as e:
        flash(str(e), "error")
    except BookingPermissionError:
        abort(403)
    return redirect(request.referrer if request.referrer and request.referrer.startswith(request.host_url)
                    else url_for("customer.history"))


@bp.route("/notifications")
@login_required
def notifications():
    items = NotificationService.for_user(current_user.id)
    return render_template("notifications.html", notifications=items)


@bp.route("/notifications/read", methods=["POST"])
@login_required
def notifications_read():
    nid = request.form.get("id", type=int)
    if nid:
        n = NotificationService.mark_read(current_user.id, nid)
        if n and n.link and n.link.startswith("/") and not n.link.startswith("//"):
            return redirect(n.link)
    else:
        NotificationService.mark_all_read(current_user.id)
    return redirect(url_for("customer.notifications"))
