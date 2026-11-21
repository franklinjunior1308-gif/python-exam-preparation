from datetime import timedelta

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import ROLE_CUSTOMER, Business, Service, StaffMember, utcnow
from ..services.availability import AvailabilityService
from ..services.booking_manager import BookingError, BookingManager
from ..utils import parse_date, parse_utc_iso, to_local

bp = Blueprint("public", __name__)


def get_business_or_404(slug):
    return Business.query.filter_by(slug=slug).first_or_404()


def active_services(business):
    return Service.query.filter_by(business_id=business.id, is_active=True).order_by(Service.name).all()


@bp.route("/")
def home():
    featured = Business.query.order_by(Business.created_at.desc()).limit(3).all()
    return render_template("public/home.html", featured=featured)


@bp.route("/businesses")
def businesses():
    q = request.args.get("q", "").strip()
    query = Business.query
    if q:
        like = f"%{q}%"
        query = query.filter(Business.name.ilike(like) | Business.category.ilike(like))
    return render_template("public/businesses.html", businesses=query.order_by(Business.name).all(), q=q)


@bp.route("/b/<slug>")
def business_profile(slug):
    b = get_business_or_404(slug)
    staff = [s for s in b.staff_members if s.is_active]
    return render_template("public/business.html", business=b, services=active_services(b), staff=staff)


@bp.route("/b/<slug>/services")
def service_list(slug):
    b = get_business_or_404(slug)
    return render_template("public/services.html", business=b, services=active_services(b))


@bp.route("/b/<slug>/book", methods=["GET", "POST"])
def book(slug):
    b = get_business_or_404(slug)
    services = active_services(b)
    if request.method == "POST":
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if current_user.role != ROLE_CUSTOMER:
            flash("Only customer accounts can make bookings. Use a customer account to book.", "error")
            return redirect(url_for("public.book", slug=slug))
        try:
            service_id = int(request.form.get("service_id", ""))
            raw_staff = request.form.get("staff_id", "")
            staff_id = int(raw_staff) if raw_staff else None
        except ValueError:
            flash("Please choose a service and a time.", "error")
            return redirect(url_for("public.book", slug=slug))
        try:
            booking = BookingManager.create_booking(
                current_user, b, service_id, staff_id,
                parse_utc_iso(request.form.get("start")), request.form.get("notes", ""))
        except BookingError as e:
            flash(str(e), "error")
            return redirect(url_for("public.book", slug=slug, service=service_id))
        flash("Your appointment is booked!", "success")
        return redirect(url_for("customer.confirmation", booking_id=booking.id))

    selected = request.args.get("service", type=int)
    staff = [{"id": s.id, "name": s.name, "title": s.title, "services": [x.id for x in s.services]}
             for s in b.staff_members if s.is_active]
    today = to_local(utcnow(), b.timezone).date()
    return render_template("public/book.html", business=b, services=services, staff=staff, selected=selected,
                           min_date=today.isoformat(),
                           max_date=(today + timedelta(days=current_app.config["BOOKING_HORIZON_DAYS"])).isoformat())


@bp.route("/api/b/<slug>/slots")
def slots(slug):
    """JSON list of available start times. Advisory only: the server re-checks on booking."""
    b = get_business_or_404(slug)
    service = Service.query.filter_by(id=request.args.get("service_id", type=int), business_id=b.id,
                                      is_active=True).first()
    day = parse_date(request.args.get("date", ""))
    if service is None or day is None:
        return jsonify(error="Invalid service or date."), 400
    staff = None
    if request.args.get("staff_id"):
        staff = StaffMember.query.filter_by(id=request.args.get("staff_id", type=int), business_id=b.id).first()
        if staff is None:
            return jsonify(error="Unknown staff member."), 400
    result = AvailabilityService.get_slots(b, service, day, staff)
    return jsonify(slots=[{
        "start": s["start"].strftime("%Y-%m-%dT%H:%M"),
        "label": to_local(s["start"], b.timezone).strftime("%H:%M"),
    } for s in result])
