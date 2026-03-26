import os
from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "production"))

def init_db():
    """Helper to initialize database tables."""
    try:
        with app.app_context():
            from app.extensions import db
            db.create_all()
            print(" * Database tables verified successfully.")
    except Exception as e:
        print(f" * WARNING: Database initialization skipped/failed: {e}")

# Call initialization on import (Gunicorn)
init_db()

if __name__ == "__main__":
    # To test HTTPS locally (required for PWA Push on mobile):
    # 1. pip install pyopenssl
    # 2. Set FLASK_SSL=1 in your .env or terminal
    use_ssl = os.environ.get("FLASK_SSL") == "1"
    
    if use_ssl:
        print(" * Starting with ad-hoc SSL certificate (HTTPS)")
        app.run(host='0.0.0.0', port=8081, ssl_context='adhoc')
    else:
        app.run(host='0.0.0.0', port=8081)
