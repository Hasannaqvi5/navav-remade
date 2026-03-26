from flask import current_app


def send_sms(unit, to_number: str, body: str) -> bool:
    """
    Send an SMS via a unit's own Twilio credentials.
    Returns True on success, False on failure.
    """
    if not all([unit.twilio_account_sid, unit.twilio_auth_token, unit.twilio_phone_number]):
        current_app.logger.warning(
            f"[SMS] Unit '{unit.name}' does not have Twilio credentials configured. SMS skipped."
        )
        return False

    try:
        from twilio.rest import Client
        client = Client(unit.twilio_account_sid, unit.twilio_auth_token)
        message = client.messages.create(
            body=body,
            from_=unit.twilio_phone_number,
            to=to_number,
        )
        current_app.logger.info(f"[SMS] Sent to {to_number} — SID: {message.sid}")
        return True
    except Exception as exc:
        current_app.logger.error(f"[SMS] Failed to send to {to_number}: {exc}")
        return False


def send_event_reminder_sms(unit, user, event) -> bool:
    """Send an event reminder SMS to a member using the unit's Twilio account."""
    if not user.phone_number or not user.notify_sms:
        return False
    body = (
        f"[{unit.name}] Reminder: {event.name} is on "
        f"{event.event_date.strftime('%b %d')}. "
        f"Please log in to NavAv to submit your response."
    )
    return send_sms(unit, user.phone_number, body)
