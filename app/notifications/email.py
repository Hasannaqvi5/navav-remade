from flask import current_app, render_template_string
from flask_mail import Message, email_dispatched
from app.extensions import mail
import os
import time

def log_email_to_file(sender, message, **kwargs):
    """Write intercepted emails to an emails/ directory for local testing."""
    app = sender
    emails_dir = os.path.join(app.root_path, '..', 'emails')
    os.makedirs(emails_dir, exist_ok=True)
    filename = f"{time.strftime('%Y%m%d-%H%M%S')}_{message.subject.replace(' ', '_').replace('/', '-')}.txt"
    filepath = os.path.join(emails_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"TO: {message.recipients}\nSUBJECT: {message.subject}\n\n{message.html}")
    app.logger.info(f"📧 Email intercepted and saved to {os.path.relpath(filepath)}")

# Connect the signal so that any call to mail.send() triggers this function
email_dispatched.connect(log_email_to_file)


def send_email(to: str, subject: str, body_html: str, body_text: str = "") -> None:
    """Send an email via Flask-Mail."""
    msg = Message(
        subject=subject,
        recipients=[to],
        html=body_html,
        body=body_text,
    )
    try:
        mail.send(msg)
    except Exception as exc:
        current_app.logger.error(f"Failed to send email to {to}: {exc}")


def send_event_reminder(user, event, unit) -> None:
    """Send a reminder email to a member about an upcoming event."""
    subject = f"[{unit.name}] Reminder: {event.name} on {event.event_date.strftime('%B %d')}"
    body_html = f"""
    <p>Hi {user.first_name},</p>
    <p>This is a reminder that <strong>{event.name}</strong> is coming up on
    <strong>{event.event_date.strftime('%B %d, %Y')}</strong>
    {f'at {event.event_time.strftime("%H:%M")}' if event.event_time else ''}.
    </p>
    <p>Please log in to NavAv to submit your attendance response before the due date.</p>
    <p>— {unit.name}</p>
    """
    send_email(user.email, subject, body_html)


def send_invite_email(invite, invite_url: str, unit_name: str) -> None:
    """Send an invite email to a new member."""
    subject = f"You've been invited to join {unit_name} on NavAv"
    body_html = f"""
    <p>You have been invited to join <strong>{unit_name}</strong> on NavAv.</p>
    <p><a href="{invite_url}">Click here to create your account</a></p>
    <p>This link expires in 48 hours.</p>
    """
    send_email(invite.email, subject, body_html)


def send_password_reset_email(user, reset_url: str) -> None:
    """Send a password reset email."""
    subject = "NavAv — Password Reset"
    body_html = f"""
    <p>Hi {user.first_name},</p>
    <p>Click the link below to reset your NavAv password. This link expires in 1 hour.</p>
    <p><a href="{reset_url}">Reset My Password</a></p>
    <p>If you did not request this, you can safely ignore this email.</p>
    """
    send_email(user.email, subject, body_html)


def send_welcome_email(user) -> None:
    """Send a welcome email to a new user after registration."""
    subject = "Welcome to NavAv!"
    body_html = f"""
    <p>Hi {user.first_name},</p>
    <p>Welcome to <strong>NavAv</strong>! Your account has been successfully created.</p>
    <p>You can now log in to view your organizations, events, and manage your attendance.</p>
    <p>We're excited to have you on board.</p>
    <br>
    <p>— The NavAv Team</p>
    """
    send_email(user.email, subject, body_html)
