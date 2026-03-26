from app import create_app
from app.models.unit import Unit
from app.models.event import Event
from app.extensions import db
from datetime import datetime, time

app = create_app()
with app.app_context():
    unit = Unit.query.first()
    event = Event.query.filter_by(unit_id=unit.id).first()
    
    if not event:
        # Create a dummy event for testing
        event = Event(
            unit_id=unit.id,
            created_by=unit.members[0].user_id,
            name="Test Event",
            event_date=datetime.now().date(),
            event_time=time(13, 45),
            event_end_time=time(14, 0),
            response_due_date=datetime(2026, 3, 25, 13, 45)
        )
        db.session.add(event)
        db.session.commit()

    print(f"Testing for Unit: {unit.name}")
    
    # Test 24h
    unit.time_format = '24h'
    db.session.commit()
    
    # Need to manually call filters since we are in a script
    from flask import g
    # Re-import filters from app instance
    time_range_filter = app.jinja_env.filters['time_range']
    format_dt_filter = app.jinja_env.filters['format_dt']
    
    print("\n--- 24-hour Mode ---")
    print(f"Time Range: {time_range_filter(event)}")
    print(f"Deadline: {format_dt_filter(event.response_due_date, unit=unit)}")
    
    # Test 12h
    unit.time_format = '12h'
    db.session.commit()
    
    print("\n--- 12-hour Mode ---")
    print(f"Time Range: {time_range_filter(event)}")
    print(f"Deadline: {format_dt_filter(event.response_due_date, unit=unit)}")
