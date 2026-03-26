"""
app/__init__.py — Application factory for NavAv.

Using the application factory pattern (create_app) instead of a module-level
Flask instance allows us to:
  - Create multiple isolated app instances (e.g. one for tests)
  - Avoid circular imports between the app and its blueprints/models
  - Configure the app differently per environment (dev, prod, testing)
"""

import os
from flask import Flask
from config import config


def create_app(config_name: str = "default") -> Flask:
    """
    Create and configure the Flask application.

    Args:
        config_name: Key into the `config` dict in config.py.
                     Defaults to "default" (which maps to DevelopmentConfig).

    Returns:
        A fully configured Flask app instance with all extensions and
        blueprints registered.
    """
    app = Flask(__name__)

    # Load configuration from the matching Config class in config.py.
    # This sets DATABASE_URL, SECRET_KEY, MAIL_*, etc.
    app.config.from_object(config[config_name])

    # ── Extensions ────────────────────────────────────────────────────────────
    # init_app() binds each extension to this specific app instance.
    # This is the second half of the "application factory" pattern: extensions
    # are created without an app in extensions.py, then bound here.
    from app.extensions import db, migrate, login_manager, mail, csrf
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    # ── Models ────────────────────────────────────────────────────────────────
    # Import all models so Flask-Migrate (Alembic) can detect them and
    # generate migration scripts. The `noqa: F401` suppresses "imported but
    # unused" linting warnings — these imports ARE needed as a side-effect.
    from app.models import user, unit, invite, event, response, attendance  # noqa: F401

    # ── Blueprints ────────────────────────────────────────────────────────────
    # Each blueprint is a self-contained module with its own routes and templates.
    # url_prefix scopes all URLs in that blueprint (e.g. /auth/login, /admin/...).

    from app.auth import auth as auth_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")

    from app.admin import admin as admin_bp
    app.register_blueprint(admin_bp, url_prefix="/admin")

    from app.member import member as member_bp
    app.register_blueprint(member_bp, url_prefix="/member")

    # ── Global Routes ─────────────────────────────────────────────────────────
    from flask import redirect, url_for
    from flask_login import current_user

    @app.route("/")
    def index():
        """
        Landing page redirect.
        If a logged-in user is authenticated, bounce them to their dashboard
        (where they can see their unit, or create/join a unit).
        Otherwise redirect to the login page like NAVAV.
        """
        if current_user.is_authenticated:
            return redirect(url_for("member.dashboard"))
        return redirect(url_for("auth.login"))

    # ── Template Filters ──────────────────────────────────────────────────────
    @app.template_filter('time_range')
    def time_range_filter(event):
        """Format event times into 'From 7pm to 10pm' or 'at 7pm'"""
        if not event.event_time:
            return ""
            
        is_24h = event.unit.time_format == '24h'
        
        def format_t(t):
            if is_24h:
                return t.strftime("%H:%M")
            
            res = t.strftime("%I:%M %p").lower().lstrip("0")
            if res.endswith(":00 am"):
                return res.replace(":00 am", "am")
            if res.endswith(":00 pm"):
                return res.replace(":00 pm", "pm")
            return res.replace(" ", "")

        start = format_t(event.event_time)
        if event.event_end_time:
            end = format_t(event.event_end_time)
            return f"From {start} to {end}"
        return f"at {start}"

    @app.template_filter('format_dt')
    def format_dt_filter(dt, unit=None):
        """Format a datetime object based on the unit's time_format."""
        if not dt:
            return ""
        
        is_24h = True
        if unit and hasattr(unit, 'time_format'):
            is_24h = unit.time_format == '24h'
            
        time_part = dt.strftime("%H:%M") if is_24h else dt.strftime("%I:%M%p").lower().lstrip("0")
        return f"{dt.strftime('%d %b')} at {time_part}"

    # ── PWA Service Worker ────────────────────────────────────────────────────
    from flask import send_from_directory
    @app.route('/sw.js')
    def serve_sw():
        return send_from_directory(os.path.join(app.root_path, 'static', 'js'), 'sw.js', mimetype='application/javascript')

    # ── CLI Commands ──────────────────────────────────────────────────────────
    @app.cli.command("send-reminders")
    def send_reminders():
        """Manually trigger automated RSVP reminders for all units."""
        from app.utils.notifications import send_deadline_reminders
        count = send_deadline_reminders()
        print(f"Automated check complete. Sent {count} reminders.")

    return app
