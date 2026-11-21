from datetime import timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func

from ..extensions import db
from ..models import (ROLE_ADMIN, ROLE_STAFF, STATUS_CANCELLED, STATUS_COMPLETED, STATUS_CONFIRMED, Booking,
                      Service, StaffMember, User, WorkSchedule, utcnow)
from ..services.booking_manager import BookingError, BookingManager, BookingPermissionError
from ..utils import (EMAIL_RE, WEEKDAYS, local_to_utc, parse_date, parse_price_to_cents, parse_time,
                     roles_required, to_local)
from datetime import time

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
@roles_required(ROLE_ADMIN)
def _admin_only():
    pass


def biz():
    b = current_user.business
    if b is None:
        abort(404)
    return b


# Every lookup below is scoped by business_id: another business's record is simply a 404.
def own_service(service_id):
    return Service.query.filter_by(id=service_id, business_id=biz().id).first_or_404()


def own_staff(staff_id):
    return StaffMember.query.filter_by(id=staff_id, business_id=biz().id).first_or_404()


def own_booking(booking_id):
    return Booking.query.filter_by(id=booking_id, business_id=biz().id).first_or_404()


@bp.route("")
def dashboard():
    b = biz()
    now = utcnow()
    base = Booking.query.filter_by(business_id=b.id)
    by_status = dict(db.session.query(Booking.status, func.count(Booking.id))
                     .filter(Booking.business_id == b.id).group_by(Booking.status).all())
    revenue = (db.session.query(func.coalesce(func.sum(Booking.price_cents), 0))
               .filter(Booking.business_id == b.id, Booking.status == STATUS_COMPLETED).scalar())
    upcoming_value = (db.session.query(func.coalesce(func.sum(Booking.price_cents), 0))
                      .filter(Booking.business_id == b.id, Booking.status == STATUS_CONFIRMED,
                              Booking.start_time >= now).scalar())
    upcoming = (base.filter(Booking.status == STATUS_CONFIRMED, Booking.start_time >= now)
                .order_by(Booking.start_time).limit(6).all())
    top = (db.session.query(Service.name, func.count(Booking.id).label("n"))
           .join(Booking, Booking.service_id == Service.id)
           .filter(Booking.business_id == b.id, Booking.status != STATUS_CANCELLED)
           .group_by(Service.id).order_by(func.count(Booking.id).desc()).limit(5).all())
    stats = {
        "total": sum(by_status.values()),
        "confirmed": by_status.get(STATUS_CONFIRMED, 0),
        "completed": by_status.get(STATUS_COMPLETED, 0),
        "cancelled": by_status.get(STATUS_CANCELLED, 0),
        "revenue": revenue, "upcoming_value": upcoming_value,
        "services": Service.query.filter_by(business_id=b.id, is_active=True).count(),
        "staff": StaffMember.query.filter_by(business_id=b.id, is_active=True).count(),
    }
    setup_done = stats["services"] > 0 and stats["staff"] > 0 and (
        WorkSchedule.query.join(StaffMember).filter(StaffMember.business_id == b.id).count() > 0)
    return render_template("admin/dashboard.html", business=b, stats=stats, upcoming=upcoming, top=top,
                           setup_done=setup_done)


# ---- business settings -----------------------------------------------------------------
@bp.route("/settings", methods=["GET", "POST"])
def settings():
    b = biz()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not (2 <= len(name) <= 120):
            flash("Business name must be 2-120 characters.", "error")
        else:
            b.name = name
            b.description = request.form.get("description", "").strip()[:1000]
            b.address = request.form.get("address", "").strip()[:200]
            b.phone = request.form.get("phone", "").strip()[:40]
            db.session.commit()
            flash("Business profile updated.", "success")
            return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html", business=b)


# ---- services --------------------------------------------------------------------------
def read_service_form(form):
    errors = []
    name = form.get("name", "").strip()
    if not (2 <= len(name) <= 120):
        errors.append("Service name must be 2-120 characters.")
    price = parse_price_to_cents(form.get("price", ""))
    if price is None:
        errors.append("Enter a valid price (0 or more).")
    try:
        duration = int(form.get("duration", ""))
        if not (5 <= duration <= 600):
            raise ValueError
    except ValueError:
        duration = None
        errors.append("Duration must be a whole number of minutes between 5 and 600.")
    return {"name": name, "description": form.get("description", "").strip()[:1000],
            "price_cents": price, "duration_minutes": duration}, errors


@bp.route("/services")
def services():
    items = Service.query.filter_by(business_id=biz().id).order_by(Service.is_active.desc(), Service.name).all()
    return render_template("admin/services.html", services=items)


@bp.route("/services/new", methods=["GET", "POST"])
def service_new():
    if request.method == "POST":
        data, errors = read_service_form(request.form)
        if not errors:
            db.session.add(Service(business_id=biz().id, **data))
            db.session.commit()
            flash("Service created.", "success")
            return redirect(url_for("admin.services"))
        for e in errors:
            flash(e, "error")
    return render_template("admin/service_form.html", service=None, form=request.form)


@bp.route("/services/<int:service_id>/edit", methods=["GET", "POST"])
def service_edit(service_id):
    s = own_service(service_id)
    if request.method == "POST":
        data, errors = read_service_form(request.form)
        if not errors:
            for k, v in data.items():
                setattr(s, k, v)
            db.session.commit()
            flash("Service updated. Existing bookings keep their original price.", "success")
            return redirect(url_for("admin.services"))
        for e in errors:
            flash(e, "error")
    return render_template("admin/service_form.html", service=s, form=request.form)


@bp.route("/services/<int:service_id>/toggle", methods=["POST"])
def service_toggle(service_id):
    s = own_service(service_id)
    s.is_active = not s.is_active
    db.session.commit()
    flash(f"Service {'activated' if s.is_active else 'deactivated'}.", "success")
    return redirect(url_for("admin.services"))


# ---- staff -----------------------------------------------------------------------------
def selected_services(form):
    ids = {int(i) for i in form.getlist("services") if i.isdigit()}
    return Service.query.filter(Service.business_id == biz().id, Service.id.in_(ids)).all() if ids else []


@bp.route("/staff")
def staff_list():
    items = StaffMember.query.filter_by(business_id=biz().id).all()
    return render_template("admin/staff.html", staff=items)


@bp.route("/staff/new", methods=["GET", "POST"])
def staff_new():
    all_services = Service.query.filter_by(business_id=biz().id, is_active=True).order_by(Service.name).all()
    if request.method == "POST":
        errors = []
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not (2 <= len(name) <= 120):
            errors.append("Name must be 2-120 characters.")
        if not EMAIL_RE.match(email):
            errors.append("Enter a valid email address.")
        elif User.query.filter_by(email=email).first():
            errors.append("An account with this email already exists.")
        if len(password) < current_app.config["MIN_PASSWORD_LENGTH"]:
            errors.append(f"Temporary password must be at least {current_app.config['MIN_PASSWORD_LENGTH']} characters.")
        if not errors:
            user = User(name=name, email=email, role=ROLE_STAFF)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            member = StaffMember(business_id=biz().id, user_id=user.id,
                                 title=request.form.get("title", "").strip()[:80])
            member.services = selected_services(request.form)
            db.session.add(member)
            db.session.commit()
            flash(f"{name} was added. Next, set their working hours.", "success")
            return redirect(url_for("admin.staff_schedule", staff_id=member.id))
        for e in errors:
            flash(e, "error")
    return render_template("admin/staff_form.html", member=None, all_services=all_services, form=request.form)


@bp.route("/staff/<int:staff_id>/edit", methods=["GET", "POST"])
def staff_edit(staff_id):
    m = own_staff(staff_id)
    all_services = Service.query.filter_by(business_id=biz().id, is_active=True).order_by(Service.name).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not (2 <= len(name) <= 120):
            flash("Name must be 2-120 characters.", "error")
        else:
            m.user.name = name
            m.title = request.form.get("title", "").strip()[:80]
            m.services = selected_services(request.form)
            db.session.commit()
            flash("Staff member updated.", "success")
            return redirect(url_for("admin.staff_list"))
    return render_template("admin/staff_form.html", member=m, all_services=all_services, form=request.form)


@bp.route("/staff/<int:staff_id>/toggle", methods=["POST"])
def staff_toggle(staff_id):
    m = own_staff(staff_id)
    m.is_active = not m.is_active
    m.user.is_active_account = m.is_active
    db.session.commit()
    flash(f"{m.name} {'reactivated' if m.is_active else 'deactivated'}.", "success")
    return redirect(url_for("admin.staff_list"))


@bp.route("/staff/<int:staff_id>/schedule", methods=["GET", "POST"])
def staff_schedule(staff_id):
    m = own_staff(staff_id)
    if request.method == "POST":
        errors, blocks = [], []
        for i, day in enumerate(WEEKDAYS):
            if request.form.get(f"work_{i}"):
                start, end = parse_time(request.form.get(f"start_{i}")), parse_time(request.form.get(f"end_{i}"))
                if not start or not end or end <= start:
                    errors.append(f"{day}: end time must be after start time.")
                else:
                    blocks.append(WorkSchedule(weekday=i, start_time=start, end_time=end))
        if not errors:
            # delete first so the (staff, weekday) unique constraint never trips on flush order
            WorkSchedule.query.filter_by(staff_id=m.id).delete()
            db.session.expire(m, ["schedules"])
            for blk in blocks:
                blk.staff_id = m.id
                db.session.add(blk)
            db.session.commit()
            flash("Working schedule saved.", "success")
            return redirect(url_for("admin.staff_list"))
        for e in errors:
            flash(e, "error")
    current = {w.weekday: w for w in m.schedules}
    return render_template("admin/schedule.html", member=m, current=current, form=request.form,
                           defaults=(time(9, 0), time(17, 0)))


# ---- bookings & calendar ---------------------------------------------------------------
@bp.route("/calendar")
def calendar():
    b = biz()
    today = to_local(utcnow(), b.timezone).date()
    anchor = parse_date(request.args.get("week", "")) or today
    monday = anchor - timedelta(days=anchor.weekday())
    staff_id = request.args.get("staff_id", type=int)
    start = local_to_utc(monday, time(0, 0), b.timezone)
    end = local_to_utc(monday + timedelta(days=7), time(0, 0), b.timezone)
    q = Booking.query.filter(Booking.business_id == b.id, Booking.start_time >= start, Booking.start_time < end)
    if staff_id:
        q = q.filter(Booking.staff_id == staff_id)
    days = {monday + timedelta(days=i): [] for i in range(7)}
    for bk in q.order_by(Booking.start_time).all():
        days[to_local(bk.start_time, b.timezone).date()].append(bk)
    return render_template("admin/calendar.html", business=b, days=days, today=today, monday=monday,
                           prev_week=monday - timedelta(days=7), next_week=monday + timedelta(days=7),
                           staff=StaffMember.query.filter_by(business_id=b.id).all(), staff_id=staff_id)


@bp.route("/bookings")
def bookings():
    b = biz()
    status = request.args.get("status", "")
    q = Booking.query.filter_by(business_id=b.id)
    if status in ("confirmed", "completed", "cancelled"):
        q = q.filter_by(status=status)
    return render_template("admin/bookings.html", bookings=q.order_by(Booking.start_time.desc()).limit(200).all(),
                           status=status)


@bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
def booking_cancel(booking_id):
    try:
        BookingManager.cancel_booking(current_user, own_booking(booking_id))
        flash("Booking cancelled. The customer was notified.", "success")
    except BookingError as e:
        flash(str(e), "error")
    except BookingPermissionError:
        abort(403)
    return redirect(request.referrer if request.referrer and request.referrer.startswith(request.host_url)
                    else url_for("admin.bookings"))


@bp.route("/bookings/<int:booking_id>/complete", methods=["POST"])
def booking_complete(booking_id):
    try:
        BookingManager.complete_booking(current_user, own_booking(booking_id))
        flash("Booking marked as finished.", "success")
    except BookingError as e:
        flash(str(e), "error")
    except BookingPermissionError:
        abort(403)
    return redirect(request.referrer if request.referrer and request.referrer.startswith(request.host_url)
                    else url_for("admin.bookings"))
