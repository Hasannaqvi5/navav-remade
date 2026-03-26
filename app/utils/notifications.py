import json
from flask import current_app, url_for
from pywebpush import webpush, WebPushException
from app.extensions import db
from app.models.push_subscription import PushSubscription
from datetime import datetime, timezone, timedelta

def send_push_to_subscription(subscription, title, body, url=None):
    """
    Sends a single push notification to a specific device subscription.
    """
    try:
        vapid_private_key = current_app.config.get("VAPID_PRIVATE_KEY")
        vapid_claims = {
            "sub": f"mailto:{current_app.config.get('VAPID_ADMIN_EMAIL', 'admin@navav.app')}"
        }

        webpush(
            subscription_info=subscription.to_json(),
            data=json.dumps({
                "title": title,
                "body": body,
                "url": url or "/"
            }),
            vapid_private_key=vapid_private_key,
            vapid_claims=vapid_claims,
            ttl=86400  # 24 hours
        )
        # Update last_used
        subscription.last_used = datetime.now(timezone.utc)
        db.session.commit()
        return True
    except WebPushException as ex:
        # If the subscription is no longer valid (e.g. user revoked permission or cleared cache),
        # we should probably remove it from our database.
        if ex.response and ex.response.status_code in [404, 410]:
            print(f"Removing expired subscription {subscription.id}")
            db.session.delete(subscription)
            db.session.commit()
        else:
            print(f"WebPush error: {ex}")
        return False
    except Exception as ex:
        print(f"Error sending push: {ex}")
        return False

def send_new_event_notification(event):
    """
    Notifies all members of a unit when a new event is created.
    """
    # Find all members of the unit who have push subscriptions
    from app.models.unit import UnitMember
    members = UnitMember.query.filter_by(unit_id=event.unit_id).all()
    
    title = f"New Event: {event.name}"
    time_str = event.event_time.strftime('%H:%M') if event.event_time else "TBD"
    body = f"{event.event_date.strftime('%b %d')} at {time_str} — RSVP now!"
    url = url_for('member.event_detail', event_id=event.id)

    count = 0
    for member in members:
        for sub in member.user.push_subscriptions:
            if send_push_to_subscription(sub, title, body, url):
                count += 1
    
    return count

def send_deadline_reminders(unit_id=None, force=False):
    """
    Finds events with RSVP deadlines in the next 24-48 hours 
    and pings members who haven't responded yet.
    """
    now = datetime.now(timezone.utc)
    
    from app.models.event import Event
    from app.models.response import EventResponse
    
    if force:
        # Manual trigger: find ALL upcoming events with a deadline that hasn't passed
        query = Event.query.filter(
            Event.response_due_date > now
        )
    else:
        # Automated trigger: specifically 24h before
        query = Event.query.filter(
            Event.response_due_date > now,
            Event.response_due_date <= now + timedelta(hours=24),
            Event.reminder_sent == False
        )
    
    if unit_id:
        query = query.filter_by(unit_id=unit_id)
        
    upcoming_events = query.all()
    
    sent_count = 0
    total_notifications = 0
    for event in upcoming_events:
        from app.models.unit import UnitMember
        members = UnitMember.query.filter_by(unit_id=event.unit_id).all()
        if force:
            title = "RSVP Reminder"
            body = f"You have not responded to '{event.name}'"
        else:
            title = "RSVP Deadline Soon"
            body = f"The RSVP deadline for '{event.name}' is in less than 24 hours."
            
        url = url_for('member.event_detail', event_id=event.id)
        
        event_pings = 0
        for member in members:
            # Check if user already responded (if it's not attending/not attending)
            response = EventResponse.query.filter_by(event_id=event.id, user_id=member.user_id).first()
            if not response or response.status == 'unresponsive':
                for sub in member.user.push_subscriptions:
                    if send_push_to_subscription(sub, title, body, url):
                        total_notifications += 1
                        event_pings += 1
        
        if event_pings > 0:
            event.reminder_sent = True
            sent_count += 1
    
    db.session.commit()
    return total_notifications
