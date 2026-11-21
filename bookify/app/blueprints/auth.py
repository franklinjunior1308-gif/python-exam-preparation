from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import ROLE_ADMIN, ROLE_CUSTOMER, Business, User
from ..utils import EMAIL_RE, is_safe_redirect, slugify, valid_timezone

bp = Blueprint("auth", __name__)

BUSINESS_CATEGORIES = ["Barbershop", "Beauty salon", "Tutoring", "Wellness", "Consulting", "Other"]
COMMON_TIMEZONES = ["UTC", "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Istanbul",
                    "Asia/Almaty", "Asia/Bishkek", "Asia/Dubai", "Asia/Singapore",
                    "America/New_York", "America/Chicago", "America/Los_Angeles", "Australia/Sydney"]


def home_for(user):
    if user.is_admin:
        return url_for("admin.dashboard")
    if user.is_staff_member:
        return url_for("staff.dashboard")
    return url_for("customer.dashboard")


def validate_account(form, errors):
    name = form.get("name", "").strip()
    email = form.get("email", "").strip().lower()
    password = form.get("password", "")
    min_len = current_app.config["MIN_PASSWORD_LENGTH"]
    if not (2 <= len(name) <= 120):
        errors.append("Please enter your name (2-120 characters).")
    if not EMAIL_RE.match(email) or len(email) > 254:
        errors.append("Please enter a valid email address.")
    elif User.query.filter_by(email=email).first():
        errors.append("An account with this email already exists.")
    if len(password) < min_len:
        errors.append(f"Password must be at least {min_len} characters.")
    elif password != form.get("confirm_password", ""):
        errors.append("Passwords do not match.")
    return name, email, password


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(home_for(current_user))
    if request.method == "POST":
        errors = []
        name, email, password = validate_account(request.form, errors)
        if not errors:
            user = User(name=name, email=email, role=ROLE_CUSTOMER,
                        phone=request.form.get("phone", "").strip()[:40])
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Welcome to Bookify! Your account is ready.", "success")
            return redirect(url_for("customer.dashboard"))
        for e in errors:
            flash(e, "error")
    return render_template("auth/register.html")


@bp.route("/register-business", methods=["GET", "POST"])
def register_business():
    if current_user.is_authenticated:
        return redirect(home_for(current_user))
    if request.method == "POST":
        errors = []
        name, email, password = validate_account(request.form, errors)
        biz_name = request.form.get("business_name", "").strip()
        category = request.form.get("category", "Other")
        tz = request.form.get("timezone", "")
        if not (2 <= len(biz_name) <= 120):
            errors.append("Please enter a business name (2-120 characters).")
        if category not in BUSINESS_CATEGORIES:
            category = "Other"
        if not valid_timezone(tz):
            errors.append("Please choose a valid time zone.")
        if not errors:
            slug, i = slugify(biz_name), 1
            while Business.query.filter_by(slug=slug).first():
                i += 1
                slug = f"{slugify(biz_name)}-{i}"
            user = User(name=name, email=email, role=ROLE_ADMIN)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            db.session.add(Business(owner_id=user.id, name=biz_name, slug=slug, category=category,
                                    timezone=tz,
                                    slot_interval_minutes=current_app.config["SLOT_INTERVAL_MINUTES"]))
            db.session.commit()
            login_user(user)
            flash("Your business is set up. Add your services and staff to start taking bookings.", "success")
            return redirect(url_for("admin.dashboard"))
        for e in errors:
            flash(e, "error")
    return render_template("auth/register_business.html", categories=BUSINESS_CATEGORIES,
                           timezones=COMMON_TIMEZONES, default_tz=current_app.config["DEFAULT_TIMEZONE"])


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(home_for(current_user))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and user.is_active_account and user.check_password(request.form.get("password", "")):
            login_user(user, remember=bool(request.form.get("remember")))
            nxt = request.args.get("next")
            return redirect(nxt if is_safe_redirect(nxt) else home_for(user))
        flash("Invalid email or password.", "error")
    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("public.home"))
