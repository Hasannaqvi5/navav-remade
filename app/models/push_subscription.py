from app.extensions import db
from datetime import datetime, timezone

class PushSubscription(db.Model):
    """
    Stores Web Push subscription details for a user's specific device/browser.
    A user can have multiple subscriptions (e.g. phone, tablet, desktop).
    """
    __tablename__ = "push_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    
    # The unique URL provided by the push service (Google, Mozilla, etc.)
    endpoint = db.Column(db.Text, nullable=False)
    
    # Public key (p256dh) and Auth secret provided by the browser
    p256dh = db.Column(db.String(255), nullable=False)
    auth = db.Column(db.String(255), nullable=False)
    
    # Metadata
    device_name = db.Column(db.String(100)) # Optional: e.g. "Chrome on Android"
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_used = db.Column(db.DateTime(timezone=True))

    # Relationship back to the user
    user = db.relationship("User", back_populates="push_subscriptions")

    def __repr__(self):
        return f"<PushSubscription {self.id} for User {self.user_id}>"

    def to_json(self):
        """Returns the format expected by pywebpush."""
        return {
            "endpoint": self.endpoint,
            "keys": {
                "p256dh": self.p256dh,
                "auth": self.auth
            }
        }
