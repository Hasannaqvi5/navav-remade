from app import create_app
from app.models.unit import Unit
from app.models.event import Event
app = create_app()
with app.app_context():
    unit = Unit.query.first()
    event = Event.query.filter_by(unit_id=unit.id).first()
    print(f"UNIT_ID: {unit.id}")
    if event:
        print(f"EVENT_ID: {event.id}")
