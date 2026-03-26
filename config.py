import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    APP_NAME = os.environ.get("APP_NAME", "NavAv")

    # Flask-WTF CSRF protection — uses SECRET_KEY to sign CSRF tokens.
    # Always True; to disable in tests use app.config["WTF_CSRF_ENABLED"] = False.
    WTF_CSRF_ENABLED = True


    # ── Database ──────────────────────────────────────────────────────────────
    _db_url = os.environ.get("DATABASE_URL")
    # Render/Heroku provide 'postgres://', but SQLAlchemy requires 'postgresql://'
    if _db_url and _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    
    # If using Postgres on Render, we might need to enforce SSL
    if _db_url and "postgresql" in _db_url and "sslmode" not in _db_url:
        _db_url += ("&" if "?" in _db_url else "?") + "sslmode=require"
    
    SQLALCHEMY_DATABASE_URI = _db_url or "sqlite:///navav.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Mail ─────────────────────────────────────────────────────────────────
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True") == "True"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")

    # ── Push Notifications ───────────────────────────────────────────────────
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY")
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY")
    VAPID_ADMIN_EMAIL = os.environ.get("VAPID_ADMIN_EMAIL")

    # ── Invite / Reset token expiry ───────────────────────────────────────────
    INVITE_TOKEN_MAX_AGE = 60 * 60 * 48  # 48 hours in seconds
    RESET_TOKEN_MAX_AGE = 60 * 60 * 1    # 1 hour in seconds


class DevelopmentConfig(Config):
    DEBUG = True
    MAIL_SUPPRESS_SEND = True  # Don't try to send real emails in dev


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
