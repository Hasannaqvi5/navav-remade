import uuid
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager


class User(UserMixin, db.Model):
    """
    Represents a person with a NavAv account.

    Inherits from UserMixin, which provides default implementations for the
    is_authenticated, is_active, is_anonymous, and get_id() methods that
    Flask-Login requires.
    """
    __tablename__ = "users"

    # We use a UUID string as the primary key instead of an auto-incrementing
    # integer. This makes IDs unguessable (important for security) and avoids
    # collisions if records are ever merged across databases.
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Email is the primary login credential and must be globally unique.
    # index=True creates a DB index so lookups by email are fast.
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)

    # We never store the plaintext password — only a bcrypt hash generated
    # by Werkzeug. See set_password() / check_password() below.
    password_hash = db.Column(db.String(255), nullable=False)

    # ── Profile fields ────────────────────────────────────────────────────────
    # first_name and last_name are required at registration.
    # The rest are optional and can be filled in from the profile page later.
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(100))             # e.g. "Lead", "Manager", "Specialist"
    reference_id = db.Column(db.String(50))      # Employee or reference number
    department = db.Column(db.String(100))       # e.g. "Operations", "Supply"
    specialty = db.Column(db.String(100))        # e.g. "Software Engineering", "Logistics"
    joining_date = db.Column(db.Date)            # Date joined the organization
    profile_photo = db.Column(db.String(255))    # Relative path to uploaded file

    # ── Notification preferences ──────────────────────────────────────────────
    # Users can opt in/out of email and SMS reminders for events.
    notify_email = db.Column(db.Boolean, default=True, nullable=False)
    notify_sms = db.Column(db.Boolean, default=False, nullable=False)
    phone_number = db.Column(db.String(20))      # Required if notify_sms is True

    # ── Account status ────────────────────────────────────────────────────────
    # is_active = False suspends login without deleting the account.
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime(timezone=True))  # Updated on each successful login

    # ── Relationships ─────────────────────────────────────────────────────────
    # cascade="all, delete-orphan" means that if a User is deleted, all of
    # their related UnitMember rows, responses, and attendance records are
    # automatically deleted too (no orphan rows left in the DB).
    memberships = db.relationship("UnitMember", back_populates="user", cascade="all, delete-orphan")
    event_responses = db.relationship("EventResponse", back_populates="user", cascade="all, delete-orphan")
    attendance_records = db.relationship("AttendanceRecord", back_populates="user", cascade="all, delete-orphan", foreign_keys="[AttendanceRecord.user_id]")
    push_subscriptions = db.relationship("PushSubscription", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        """Hash a plaintext password and store it. Never stores the raw password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Compare a plaintext password against the stored hash. Returns True if they match."""
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self) -> str:
        """Returns 'First Last' — used in templates and exports."""
        return f"{self.first_name} {self.last_name}"

    @property
    def display_name(self) -> str:
        """
        Returns title + last name (e.g. 'Lead Smith') when a title is set,
        otherwise falls back to full_name. Used in the attendance sheet.
        """
        if self.title:
            return f"{self.title} {self.last_name}"
        return self.full_name

    def __repr__(self) -> str:
        """Developer-friendly string representation shown in the Python REPL."""
        return f"<User {self.email}>"


# Flask-Login calls this function on every request to reload the logged-in
# user from the session. It receives the user_id that was stored in the
# session cookie and must return the corresponding User object (or None).
@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, user_id)
