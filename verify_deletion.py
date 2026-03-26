canfrom app import create_app
from app.models.unit import Unit
from app.models.event import Event
from app.models.user import User
from app.extensions import db
from datetime import datetime

app = create_app()
with app.app_context():
    # 1. Create a test organization
    test_unit = Unit(name="Deletion Test Org")
    db.session.add(test_unit)
    db.session.commit()
    test_id = test_unit.id
    
    # 2. Add a dummy event
    user = User.query.first()
    test_event = Event(
        unit_id=test_id,
        created_by=user.id,
        name="Test Event",
        event_date=datetime.now().date()
    )
    db.session.add(test_event)
    db.session.commit()
    event_id = test_event.id
    
    # 3. Perform Deletion
    unit_to_del = db.session.get(Unit, test_id)
    db.session.delete(unit_to_del)
    db.session.commit()
    
    if db.session.get(Unit, test_id) is None and db.session.get(Event, event_id) is None:
        print("SUCCESS: Database cascading deletion verified.")
    else:
        print("FAILURE: Database deletion incomplete.")

    # 4. Check template rendering within request context
    with app.test_request_context('/admin/unit/123/settings'):
        rendered = app.jinja_env.get_template('admin/settings.html').render(
            unit=Unit.query.first(),
            csrf_token=lambda: "token"
        )
        if "Danger Zone" in rendered and "delete_unit" in rendered:
            print("SUCCESS: Danger Zone UI verified.")
        else:
            print("FAILURE: Danger Zone UI missing.")
