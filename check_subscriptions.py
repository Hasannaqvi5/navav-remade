import os
import sys
from datetime import datetime, timezone

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.push_subscription import PushSubscription

def list_user_subscriptions():
    app = create_app()
    with app.app_context():
        # Find the user (assuming current test user)
        # We'll just list all subscriptions to be sure
        subs = PushSubscription.query.all()
        print(f"--- Total Subscriptions in DB: {len(subs)} ---")
        for sub in subs:
            user = User.query.get(sub.user_id)
            print(f"User: {user.email}")
            print(f"  ID: {sub.id}")
            print(f"  Created: {sub.created_at}")
            print(f"  Endpoint: {sub.endpoint[:50]}...")
            print("-" * 30)

if __name__ == "__main__":
    list_user_subscriptions()
