from flask_login import current_user

from .services.notifications import NotificationService
from .utils import WEEKDAYS, duration_label, money, to_local


def register_template_helpers(app):
    @app.template_filter("money")
    def _money(cents):
        return money(cents)

    @app.template_filter("duration")
    def _duration(minutes):
        return duration_label(minutes)

    @app.template_filter("localdt")
    def _localdt(dt, tzname, fmt="%a %d %b %Y, %H:%M"):
        return to_local(dt, tzname).strftime(fmt) if dt else ""

    @app.context_processor
    def inject_globals():
        unread = 0
        if current_user.is_authenticated:
            unread = NotificationService.unread_count(current_user.id)
        return {"unread_count": unread, "WEEKDAYS": WEEKDAYS}
