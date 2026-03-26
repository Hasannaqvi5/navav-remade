"""
models/attendance.py — AttendanceRecord model.

An AttendanceRecord is the official, admin-confirmed record of whether a
member was physically present at an event. It is created on the evening
of the event (not in advance) by an organization admin or coordinator.

This is distinct from EventResponse (a member's self-reported RSVP).
"""

import uuid
from datetime import datetime, timezone
from app.extensions import db


class AttendanceRecord(db.Model):
    """Admin-confirmed actual attendance for a member on an event night."""
    __tablename__ = "attendance_records"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    # marked_by stores which admin confirmed attendance — used for audit trail.
    marked_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)

    # True = present, False = absent (admin confirmed no-show)
    was_present = db.Column(db.Boolean, nullable=False)
    # Optional admin notes (e.g. "late arrival", "left early", "medical")
    notes = db.Column(db.String(300))
    marked_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    event = db.relationship("Event", back_populates="attendance_records")
    user = db.relationship("User", back_populates="attendance_records", foreign_keys=[user_id])
    marker = db.relationship("User", foreign_keys=[marked_by])

    __table_args__ = (
        db.UniqueConstraint("event_id", "user_id", name="uq_attendance_record"),
    )

    def __repr__(self) -> str:
        status = "present" if self.was_present else "absent"
        return f"<AttendanceRecord user={self.user_id} event={self.event_id} {status}>"
