"""
models/unit.py — Unit and UnitMember models.

━━━ What these models represent ━━━

  Organization → A single organisation (e.g. Community Center).
               Think "organization" — it owns events and has members.

  UnitMember → The join table between User ↔ Organization with an extra `role` field.
               One row = one person's membership in one unit.
               A person can be a member of multiple units (e.g. serves multiple
               detachments), which is why this is a many-to-many relationship
               rather than a FK directly on User.

━━━ New in Phase 3: Shareable join links ━━━

  join_token       → A random 64-char secret token embedded in the join URL.
                     Anyone who has the URL can join the unit as a member.
                     Admins can regenerate this token to invalidate old links.

  join_link_enabled → Boolean toggle. When False, the join link is disabled
                      even if the token still exists. Useful for temporarily
                      pausing new member signups without losing the token.
"""

import uuid
import secrets  # Used to generate a cryptographically random join token
from datetime import datetime, timezone
from app.extensions import db


class Unit(db.Model):
    """
    An organization (e.g. Community Club, Volunteer Group).

    Created by the first admin who sets it up on NavAv.
    Other users join it either via:
      1. A shareable join link  (/auth/join/<join_token>)
      2. An individual email invite (/auth/register/invite?token=...)
    """
    __tablename__ = "units"

    # UUID primary key — see user.py for why UUIDs are preferred over integers
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # The organization's official name, displayed in the navbar and throughout the app
    name        = db.Column(db.String(200), nullable=False)
    city        = db.Column(db.String(100))          # City the organization is based in
    province    = db.Column(db.String(50))           # Province abbreviation (e.g. "ON")
    description = db.Column(db.Text)                 # Optional blurb shown on the organization page
    created_at  = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # ── Shareable join link ────────────────────────────────────────────────────
    # join_token is a random 64-character URL-safe string (not a signed JWT —
    # it's just a hard-to-guess random key). It is looked up directly in the DB
    # when processing a join request.
    #
    # Why not use itsdangerous here?
    #   - The join link is meant to be reusable (many people, one link).
    #   - Signed tokens expire, which we don't want for an open-invite link.
    #   - A random DB-stored token can be instantly invalidated by regenerating it.
    join_token        = db.Column(db.String(64), nullable=True)
    # Admins can flip this to False to pause new member joins without losing the token
    join_link_enabled = db.Column(db.Boolean, default=True, nullable=False)

    admin_join_token        = db.Column(db.String(64), nullable=True)
    admin_join_link_enabled = db.Column(db.Boolean, default=True, nullable=False)
    
    # ── Display Settings ───────────────────────────────────────────────────────
    # '12h' (standard AM/PM) or '24h' (military)
    time_format = db.Column(db.String(5), default='12h', nullable=False)

    # ── Twilio SMS credentials ─────────────────────────────────────────────────
    # Stored per-unit so different units can send from their own phone number.
    # In production these should be stored in a secrets manager, not the DB.
    twilio_account_sid  = db.Column(db.String(255))
    twilio_auth_token   = db.Column(db.String(255))
    twilio_phone_number = db.Column(db.String(30))

    # ── Relationships ──────────────────────────────────────────────────────────
    # cascade="all, delete-orphan" means deleting a Unit also deletes all
    # its member rows, invites, and events — no orphan data left in the DB.
    members = db.relationship("UnitMember", back_populates="unit", cascade="all, delete-orphan")
    invites = db.relationship("Invite",     back_populates="unit", cascade="all, delete-orphan")
    events  = db.relationship("Event",      back_populates="unit", cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint("join_token", name="uq_unit_join_token"),
        db.UniqueConstraint("admin_join_token", name="uq_unit_admin_join_token"),
    )

    def generate_join_token(self) -> str:
        """
        Generate (or regenerate) the shareable join token.

        Uses secrets.token_urlsafe(48) which produces a 64-character
        URL-safe base64 string. Calling this again invalidates any
        previously shared links because the old token is replaced.

        Usage:
            unit.generate_join_token()
            db.session.commit()
        """
        self.join_token = secrets.token_urlsafe(48)
        return self.join_token

    def generate_admin_join_token(self) -> str:
        """Generate a shareable admin join token."""
        self.admin_join_token = secrets.token_urlsafe(48)
        return self.admin_join_token

    @property
    def join_url_token(self) -> str | None:
        """
        Return the join token only if the join link is currently enabled.
        Routes should use this property instead of reading join_token directly,
        so the enabled/disabled toggle is always respected.
        """
        if self.join_link_enabled and self.join_token:
            return self.join_token
        return None

    @property
    def admin_join_url_token(self) -> str | None:
        """Return the admin join token only if enabled."""
        if self.admin_join_link_enabled and self.admin_join_token:
            return self.admin_join_token
        return None

    def __repr__(self) -> str:
        return f"<Unit {self.name}>"


class UnitMember(db.Model):
    """
    Association table linking a User to a Unit with a role.

    We use a proper association model (rather than a simple many-to-many
    secondary table) because we need extra data on the join row:
      - role      → "admin" or "member"
      - joined_at → when this person became a member
      - approved  → soft-approval flag (useful for moderated units)

    Unique constraint: a user can only appear once per unit. Trying to add
    them a second time raises an IntegrityError at the DB level.
    """
    __tablename__ = "unit_members"

    id      = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"),  nullable=False)
    unit_id = db.Column(db.String(36), db.ForeignKey("units.id"),  nullable=False)

    # role is either "admin" (can manage events/members) or "member" (attendee only)
    role      = db.Column(db.String(20), nullable=False, default="member")
    joined_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # approved=False lets admins put new members in a pending state (not used by default)
    approved  = db.Column(db.Boolean, default=True, nullable=False)

    # ── ORM relationships ──────────────────────────────────────────────────────
    # back_populates wires the two sides of the relationship together so that
    # user.memberships and membership.user both work without extra queries.
    user = db.relationship("User", back_populates="memberships")
    unit = db.relationship("Unit", back_populates="members")

    # DB-level uniqueness: one (user, unit) pair only
    __table_args__ = (
        db.UniqueConstraint("user_id", "unit_id", name="uq_unit_member"),
    )

    @property
    def is_admin(self) -> bool:
        """Convenience check used in templates ({% if membership.is_admin %}) and route guards."""
        return self.role == "admin"

    def __repr__(self) -> str:
        return f"<UnitMember user={self.user_id} unit={self.unit_id} role={self.role}>"
