"""
models/response.py — EventResponse model.

An EventResponse is a member's RSVP to an upcoming event.
This is distinct from AttendanceRecord, which is the *actual* presence
marked by an admin on the night itself.

Flow:
  1. Admin creates an Event.
  2. Members submit an EventResponse (attending / not_attending + reason).
  3. On event night, admin marks actual AttendanceRecord for each member.
"""

import uuid
from datetime import datetime, timezone
from app.extensions import db

# ── Response status constants ───────────────────────────────────────────────
# Using named constants instead of magic strings prevents typos and makes the
# code easier to grep and refactor.
RESPONSE_ATTENDING = "attending"
RESPONSE_NOT_ATTENDING = "not_attending"

# ── Absence reason constants ─────────────────────────────────────────────
# Required when status is NOT_ATTENDING. These map to the Naval Reserve's
# standard absence categories for attendance sheet exports.
ABSENCE_LEAVE = "leave"
ABSENCE_DUTY = "duty"
ABSENCE_ILLNESS = "illness"
ABSENCE_COURSE = "course"
ABSENCE_OTHER = "other"

# Human-readable labels used in dropdowns and exports.
ABSENCE_REASONS = [
    (ABSENCE_LEAVE, "Leave"),
    (ABSENCE_DUTY, "Duty"),
    (ABSENCE_ILLNESS, "Illness"),
    (ABSENCE_COURSE, "Course"),
    (ABSENCE_OTHER, "Other"),
]


class EventResponse(db.Model):
    """A member's RSVP / response to a unit event."""
    __tablename__ = "event_responses"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)

    status = db.Column(db.String(30), nullable=False)   # attending | not_attending
    absence_reason = db.Column(db.String(30))            # leave | duty | illness | course | other
    comment = db.Column(db.String(500))                  # Free-text note (e.g. "will be 20 min late")
    responded_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # updated_at uses onupdate so it is automatically set by SQLAlchemy whenever
    # this row is modified, without us having to set it manually in route code.
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    event = db.relationship("Event", back_populates="responses")
    user = db.relationship("User", back_populates="event_responses")

    __table_args__ = (
        db.UniqueConstraint("event_id", "user_id", name="uq_event_response"),
    )

    def __repr__(self) -> str:
        return f"<EventResponse user={self.user_id} event={self.event_id} status={self.status}>"
