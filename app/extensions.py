"""
extensions.py — Flask extension singletons.

Extensions are created here WITHOUT being tied to any specific Flask app.
This is the "application factory" pattern: the actual app is created later
in create_app() (app/__init__.py), and extensions are initialised with
ext.init_app(app). This lets us create multiple app instances (e.g. one
for testing) without conflicts.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf import CSRFProtect

# db — SQLAlchemy ORM instance. All models import this to define their tables.
db = SQLAlchemy()

# migrate — Alembic wrapper. Tracks schema changes and generates migration scripts
# via `flask db migrate` / `flask db upgrade`.
migrate = Migrate()

# mail — Flask-Mail instance for sending transactional email (invite links,
# password resets). Configured via MAIL_* keys in config.py.
mail = Mail()

# login_manager — Flask-Login session handler.
#   login_view:    the endpoint name that unauthenticated users are redirected to
#   login_message: the flash message shown when a page requires login
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"

# csrf — Flask-WTF global CSRF protection. Adds csrf_token() to every template.
csrf = CSRFProtect()
