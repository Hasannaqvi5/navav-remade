"""
models/event.py — Event model.

An Event represents a single meeting or organization event. Admins create events;
members respond to them (EventResponse); and admins mark actual attendance
after the fact (Attendance Sheet).
"""

import uuid
from datetime import datetime, timezone
from app.extensions import db


class Event(db.Model):
    """A scheduled organization event."""
    __tablename__ = "events"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # The unit this event belongs to — members of this unit will be notified.
    unit_id = db.Column(db.String(36), db.ForeignKey("units.id"), nullable=False)
    # The admin user who created the event (used for audit trail).
    created_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)

    name = db.Column(db.String(200), nullable=False)      # E.g. "Weekly Parade Night"
    event_date = db.Column(db.Date, nullable=False)        # The calendar date of the event
    event_time = db.Column(db.Time)                        # Optional start time
    event_end_time = db.Column(db.Time)                    # Optional end time
    location = db.Column(db.String(255))                   # E.g. "HMCS York, Toronto"
    description = db.Column(db.Text)                       # Optional briefing notes
    # Deadline by which members should submit their attendance response.
    response_due_date = db.Column(db.DateTime(timezone=True))

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # Tracks whether the event reminder notification has been sent already,
    # so the scheduler doesn’t send duplicate reminders.
    reminder_sent = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    unit = db.relationship("Unit", back_populates="events")
    creator = db.relationship("User", foreign_keys=[created_by])
    responses = db.relationship("EventResponse", back_populates="event", cascade="all, delete-orphan")
    attendance_records = db.relationship("AttendanceRecord", back_populates="event", cascade="all, delete-orphan")

    @property
    def is_past_deadline(self) -> bool:
        if not self.response_due_date:
            return False
            
        # Compare naive stored due date with current system loal time
        now = datetime.now()
        due = self.response_due_date
        # SQLite storage might sometimes be naive anyway, but we want naive comparison
        if due.tzinfo is not None:
            due = due.replace(tzinfo=None)
            
        return now > due

    @property
    def is_past(self) -> bool:
        """True if the event date (and optional end time) has already passed."""
        # We use naive comparison here because event_date and event_time are naive
        # and represent the 'local' time of the event.
        now = datetime.now()
        today = now.date()
        
        if self.event_date < today:
            return True
        
        if self.event_date == today and self.event_end_time:
            # Check if current local time has passed the end time
            return now.time() > self.event_end_time
            
        return False

    def __repr__(self) -> str:
        return f"<Event {self.name} on {self.event_date}>"
