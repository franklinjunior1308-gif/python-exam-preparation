import re
import unicodedata
from datetime import date, datetime, time, timezone
from functools import wraps
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from flask import abort, request
from flask_login import current_user

UTC = timezone.utc
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def get_tz(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return ZoneInfo("UTC")


def valid_timezone(name):
    return name in available_timezones()


def to_local(dt_utc, tzname):
    """Naive-UTC datetime -> aware local datetime."""
    return dt_utc.replace(tzinfo=UTC).astimezone(get_tz(tzname))


def local_to_utc(local_date, local_time, tzname):
    """Local date + time -> naive-UTC datetime."""
    aware = datetime.combine(local_date, local_time, tzinfo=get_tz(tzname))
    return aware.astimezone(UTC).replace(tzinfo=None)


def parse_utc_iso(value):
    """Parse 'YYYY-MM-DDTHH:MM[:SS][Z]' into naive UTC; None if invalid."""
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt.replace(second=0, microsecond=0)


def parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def parse_time(value):
    try:
        return time.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "business"


def parse_price_to_cents(value):
    """'25', '25.5', '25.50' -> cents; None if invalid or negative."""
    try:
        cents = round(float(str(value).strip()) * 100)
    except (TypeError, ValueError):
        return None
    if cents < 0 or cents > 10_000_000:
        return None
    return cents


def is_safe_redirect(target):
    if not target:
        return False
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and ref.netloc == test.netloc


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app_login_required()
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def current_app_login_required():
    from flask import current_app

    return current_app.login_manager.unauthorized()


def money(cents):
    return f"${cents / 100:,.2f}"


def duration_label(minutes):
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h} h {m} min"
    if h:
        return f"{h} h"
    return f"{m} min"
