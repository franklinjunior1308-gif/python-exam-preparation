import os

from flask import Flask, render_template
from sqlalchemy import event
from sqlalchemy.engine import Engine

from .config import BASE_DIR, CONFIGS
from .extensions import csrf, db, login_manager, migrate


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record):
    import sqlite3

    if isinstance(dbapi_connection, sqlite3.Connection):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def create_app(config_name=None, overrides=None):
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    config_cls = CONFIGS.get(config_name, CONFIGS["development"])
    if config_name == "production":
        config_cls.validate()

    app = Flask(__name__, instance_path=str(BASE_DIR / "instance"))
    app.config.from_object(config_cls)
    if overrides:
        app.config.update(overrides)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from . import models  # noqa: F401  (register models)
    from .blueprints import admin, auth, customer, public, staff

    for bp in (public.bp, auth.bp, customer.bp, admin.bp, staff.bp):
        app.register_blueprint(bp)

    from .template_helpers import register_template_helpers

    register_template_helpers(app)
    register_error_handlers(app)

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    return app


def register_error_handlers(app):
    from flask_wtf.csrf import CSRFError

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(CSRFError)
    def csrf_error(_e):
        return render_template("errors/400.html"), 400

    @app.errorhandler(500)
    def server_error(_e):
        db.session.rollback()
        return render_template("errors/500.html"), 500
