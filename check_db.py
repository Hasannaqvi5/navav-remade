from app import create_app
from app.models.unit import Unit
app = create_app()
with app.app_context():
    unit = Unit.query.first()
    print(f"Time Format for {unit.name}: {unit.time_format}")
