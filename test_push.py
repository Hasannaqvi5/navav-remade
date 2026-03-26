import sys
import os
sys.path.append(os.getcwd())
from app import create_app
from app.models.user import User
from app.models.push_subscription import PushSubscription
from app.utils.notifications import send_push_to_subscription

app = create_app()
with app.app_context():
    # Find users with subscriptions
    subs = PushSubscription.query.all()
    print(f"Total subscriptions in DB: {len(subs)}")
    for s in subs:
        print(f"Sending test to User {s.user_id} ({s.device_name})")
        success = send_push_to_subscription(s, "Test Notification", "This is a test from Antigravity. It works!", "/")
        print(f"  Success: {success}")
