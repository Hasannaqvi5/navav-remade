import os
import sys
from datetime import datetime, timezone, timedelta

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app import create_app
from app.extensions import db
from app.models.event import Event
from app.models.unit import Unit, UnitMember
from app.utils.notifications import send_deadline_reminders, send_new_event_notification

def verify_notifications():
    app = create_app()
    app.config['SERVER_NAME'] = 'localhost:8081'
    app.config['PREFERRED_URL_SCHEME'] = 'http'
    with app.app_context():
        # 1. Find a unit with members
        unit = Unit.query.first()
        if not unit:
            print("No unit found. Create one first.")
            return

        print(f"Using unit: {unit.name}")

        # 2. Create a dummy event with a deadline in 23 hours
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(hours=23)
        event_date = (now + timedelta(days=2)).date()

        dummy_event = Event(
            unit_id=unit.id,
            created_by=UnitMember.query.filter_by(unit_id=unit.id, role='admin').first().user_id,
            name="TEST: RSVP Deadline Soon",
            event_date=event_date,
            response_due_date=deadline,
            reminder_sent=False
        )
        db.session.add(dummy_event)
        db.session.commit()
        print(f"Created dummy event with deadline at {deadline}")

        # 3. Test "New Event" notification (Instant)
        print("Testing 'New Event' notification...")
        sent_new = send_new_event_notification(dummy_event)
        print(f"Sent {sent_new} instant notification(s).")

        # 4. Test "Deadline Reminder" notification (Automated logic)
        print("Testing 'Deadline Reminder' logic...")
        sent_reminders = send_deadline_reminders(unit_id=unit.id)
        print(f"Sent {sent_reminders} automated reminder notification(s).")

        # Cleanup
        db.session.delete(dummy_event)
        db.session.commit()
        print("Cleanup done.")

if __name__ == "__main__":
    verify_notifications()
