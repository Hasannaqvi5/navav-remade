from app import create_app
from app.models.unit import Unit
from app.models.event import Event
from app.extensions import db
from datetime import datetime, time

app = create_app()
with app.app_context():
    unit = Unit.query.first()
    
    # Create a fresh afternoon event for testing
    test_event = Event(
        unit_id=unit.id,
        unit=unit, # Explicitly assign unit to avoid NoneType error in filter
        created_by=unit.members[0].user_id,
        name="Afternoon Test",
        event_date=datetime.now().date(),
        event_time=time(15, 30), # 3:30 PM
        event_end_time=time(17, 0), # 5:00 PM
        response_due_date=datetime(2026, 3, 25, 14, 45) # 2:45 PM
    )
    
    # Re-import filters from app instance
    time_range_filter = app.jinja_env.filters['time_range']
    format_dt_filter = app.jinja_env.filters['format_dt']
    
    # Test 24h
    unit.time_format = '24h'
    print("\n--- 24-hour Mode (3:30 PM case) ---")
    print(f"Time Range: {time_range_filter(test_event)}")
    print(f"Deadline: {format_dt_filter(test_event.response_due_date, unit=unit)}")
    
    # Test 12h
    unit.time_format = '12h'
    print("\n--- 12-hour Mode (3:30 PM case) ---")
    print(f"Time Range: {time_range_filter(test_event)}")
    print(f"Deadline: {format_dt_filter(test_event.response_due_date, unit=unit)}")
