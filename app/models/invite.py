"""
models/invite.py — Invite model.

Admins create Invite records and email a signed link to prospective members.
The link encodes the invite ID in an HMAC-signed token (itsdangerous) so
it can't be forged. Tokens expire after INVITE_TOKEN_MAX_AGE seconds
(default 48 hours, set in config.py).
"""

import uuid
from datetime import datetime, timezone
from app.extensions import db


class Invite(db.Model):
    """An invite record created by a unit admin for a specific email address."""
    __tablename__ = "invites"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    unit_id = db.Column(db.String(36), db.ForeignKey("units.id"), nullable=False)
    # The email that this invite was sent to. Becomes the new user's login email.
    email = db.Column(db.String(255), nullable=False)
    # The raw signed token string (stored for quick lookup / revocation).
    token = db.Column(db.String(255), unique=True, nullable=False)
    # The role the new member should receive when they accept ("admin" or "member").
    role = db.Column(db.String(20), nullable=False, default="member")
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # Hard expiry stored in the DB (mirrors the token's max_age in itsdangerous).
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    # Set when a user clicks the link and completes registration.
    accepted_at = db.Column(db.DateTime(timezone=True))
    # Prevents the same invite link from being used more than once.
    is_used = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    unit = db.relationship("Unit", back_populates="invites")

    @property
    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        # SQLite drops timezone info; ensure we are comparing aware datetimes
        exp = self.expires_at
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return now > exp

    @property
    def is_valid(self) -> bool:
        return not self.is_used and not self.is_expired

    def __repr__(self) -> str:
        return f"<Invite {self.email} -> unit={self.unit_id}>"
