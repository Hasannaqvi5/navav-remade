"""
admin/routes.py — Route handlers for the admin blueprint.

━━━ Access control ━━━
  Every route in this file is protected by TWO guards:
    1. @login_required   — Flask-Login ensures the user is authenticated
    2. _require_admin()  — our custom guard that checks the user is an *admin*
                           of the specific unit being accessed; returns 403 otherwise.

  This two-layer approach means:
    - A guest gets redirected to /auth/login
    - A logged-in regular member gets a 403 Forbidden page
    - Only a unit admin can see unit management pages

━━━ Route map ━━━
  /admin/dashboard                          — list all organizations this user administers
  /admin/unit/create                        — create a new organization (admin becomes first member)
  /admin/unit/<id>                          — organization overview / quick stats
  /admin/unit/<id>/invite                   — send individual email invites
  /admin/unit/<id>/join-link/regenerate     — (NEW) regenerate the shareable join token
  /admin/unit/<id>/join-link/toggle         — (NEW) enable / disable the join link
  /admin/unit/<id>/events                   — event list
  /admin/unit/<id>/events/create            — create a new event
  /admin/unit/<id>/events/<eid>/muster      — view attendance sheet
  /admin/unit/<id>/events/<eid>/mark-attendance — record a member's attendance
  /admin/unit/<id>/members                  — member list
  /admin/unit/<id>/settings                 — organization name / city / Twilio settings
  /admin/unit/<id>/export                   — download attendance CSV
"""

from flask import render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from app.admin import admin
from app.admin.forms import CreateUnitForm
from app.extensions import db
from app.models.unit import Unit, UnitMember
from app.models.invite import Invite
from app.models.event import Event
from app.models.response import EventResponse
from app.notifications.email import send_invite_email
from app.utils.notifications import send_new_event_notification, send_deadline_reminders
from app.models.attendance import AttendanceRecord
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timezone, timedelta



def _require_admin(unit: Unit) -> UnitMember:
    """Return the UnitMember record if current_user is an admin of this unit, else abort 403."""
    membership = UnitMember.query.filter_by(user_id=current_user.id, unit_id=unit.id).first()
    if not membership or not membership.is_admin:
        abort(403)
    return membership


# ── Dashboard & Unit Creation ───────────────────────────────────────────────────

@admin.route("/dashboard")
@login_required
def dashboard():
    """
    List all organizations where the current user serves as an admin.
    """
    memberships = UnitMember.query.filter_by(user_id=current_user.id, role="admin").all()
    units = [m.unit for m in memberships]
    return render_template("admin/dashboard.html", units=units)


@admin.route("/unit/create", methods=["GET", "POST"])
@login_required
def create_unit():
    """
    Create a new Organisation (Unit).

    This is the entry point for new users (post sign-up) to set up a unit workspace.
    Unlike other admin routes, this does NOT use _require_admin() because the unit
    doesn't exist yet!

    The current user is automatically assigned as the first 'admin'.
    A fresh join_token is also generated upon creation.
    """
    form = CreateUnitForm()

    if form.validate_on_submit():
        unit = Unit(
            name=form.name.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
        )
        
        # Turn on link joining by default and generate the first token
        unit.generate_join_token()
        db.session.add(unit)
        db.session.flush() # Secure the unit.id before committing

        # Add the creator as the first admin
        membership = UnitMember(
            user_id=current_user.id,
            unit_id=unit.id,
            role="admin",     # CRITICAL: elevate them so they can manage the unit
            approved=True     # Admins don't need approval
        )
        db.session.add(membership)
        db.session.commit()

        flash(f"Success! {unit.name} has been created.", "success")
        return redirect(url_for("admin.unit_detail", unit_id=unit.id))

    return render_template("admin/create.html", form=form)



@admin.route("/unit/<unit_id>")
@login_required
def unit_detail(unit_id: str):
    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)
    members = UnitMember.query.filter_by(unit_id=unit_id).all()
    all_events = Event.query.filter_by(unit_id=unit_id).order_by(Event.event_date.asc(), Event.event_time.asc()).all()
    upcoming_events = [e for e in all_events if not e.is_past][:5]
    return render_template("admin/unit_detail.html", unit=unit, members=members, upcoming_events=upcoming_events)


# ── Invite Members ────────────────────────────────────────────────────────────

@admin.route("/unit/<unit_id>/invite", methods=["GET", "POST"])
@login_required
def invite_member(unit_id: str):
    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)

    if request.method == "POST":
        emails_raw = request.form.get("emails", "")
        role = request.form.get("role", "member")
        emails = [e.strip().lower() for e in emails_raw.splitlines() if e.strip()]

        if not emails:
            flash("Please enter at least one email address.", "danger")
        else:
            s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
            invited = []
            for email in emails:
                invite = Invite(
                    unit_id=unit_id,
                    email=email,
                    role=role,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
                    token="",  # Placeholder — will be set below
                )
                db.session.add(invite)
                db.session.flush()
                token = s.dumps(invite.id, salt="invite")
                invite.token = token
                invited.append((email, token))

            db.session.commit()

            for email, token in invited:
                # Point to the invite-specific registration route (not open register)
                invite_url = url_for("auth.register_invite", token=token, _external=True)
                current_app.logger.info(f"[DEV] Invite for {email}: {invite_url}")
                # Actually send the email via Flask-Mail
                send_invite_email(invite=Invite.query.filter_by(token=token).first(), invite_url=invite_url, unit_name=unit.name)

            flash(f"{len(invited)} invite(s) sent.", "success")
            return redirect(url_for("admin.unit_detail", unit_id=unit_id))

    return render_template("admin/invite.html", unit=unit)


# ── Join Link Management (Phase 3) ────────────────────────────────────────────

@admin.route("/unit/<unit_id>/join-link/regenerate", methods=["POST"])
@login_required
def regenerate_join_link(unit_id: str):
    """
    Generate a new random join token for the unit, invalidating the old one.

    POST-only (not GET) — we don't want a link or image tag to accidentally
    trigger a regeneration. The settings template wraps this in a <form>.

    Use case: the admin shared the link but wants to revoke access for anyone
    who hasn't joined yet (e.g. it leaked to non-members).
    The new token is a fresh secrets.token_urlsafe(48) string.
    """
    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)       # Only admins can rotate the join token

    old_token = unit.join_token
    unit.generate_join_token() # Generates new token and writes it to unit.join_token
    db.session.commit()

    # Log so the admin can see the old token is gone
    current_app.logger.info(
        f"[JOIN LINK] Unit {unit.name}: token rotated (old={old_token[:8]}...)"
    )
    flash("Join link regenerated. The old link is now invalid.", "success")
    return redirect(url_for("admin.unit_settings", unit_id=unit_id))


@admin.route("/unit/<unit_id>/join-link/toggle", methods=["POST"])
@login_required
def toggle_join_link(unit_id: str):
    """Enable or disable the member shareable join link."""
    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)

    enable = request.form.get("enable", type=int)

    if enable == 1:
        unit.join_link_enabled = True
        if not unit.join_token:
            unit.generate_join_token()
        flash("Member join link enabled.", "success")
    else:
        unit.join_link_enabled = False
        flash("Member join link disabled.", "info")

    db.session.commit()
    return redirect(url_for("admin.unit_settings", unit_id=unit_id))


@admin.route("/unit/<unit_id>/admin-join-link/regenerate", methods=["POST"])
@login_required
def regenerate_admin_join_link(unit_id: str):
    """Regenerate the admin join token, invalidating the old one."""
    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)

    old_token = unit.admin_join_token
    unit.generate_admin_join_token()
    db.session.commit()

    current_app.logger.info(
        f"[ADMIN JOIN LINK] Unit {unit.name}: token rotated (old={str(old_token)[:8]}...)"
    )
    flash("Admin join link regenerated. The old link is now invalid.", "success")
    return redirect(url_for("admin.unit_settings", unit_id=unit_id))


@admin.route("/unit/<unit_id>/admin-join-link/toggle", methods=["POST"])
@login_required
def toggle_admin_join_link(unit_id: str):
    """Enable or disable the admin shareable join link."""
    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)

    enable = request.form.get("enable", type=int)

    if enable == 1:
        unit.admin_join_link_enabled = True
        if not unit.admin_join_token:
            unit.generate_admin_join_token()
        flash("Admin join link enabled.", "success")
    else:
        unit.admin_join_link_enabled = False
        flash("Admin join link disabled.", "info")

    db.session.commit()
    return redirect(url_for("admin.unit_settings", unit_id=unit_id))


# ── Events ────────────────────────────────────────────────────────────────────

@admin.route("/unit/<unit_id>/events")
@login_required
def events(unit_id: str):
    """
    List all upcoming events for the specific unit.
    Past events (events where event_date & event_end_time have passed) are excluded.
    """
    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)
    all_events = Event.query.filter_by(unit_id=unit_id).order_by(Event.event_date.desc(), Event.event_time.desc()).all()
    
    # 7-day threshold for "Recent"
    seven_days_ago = datetime.now().date() - timedelta(days=7)
    
    upcoming = [e for e in all_events if not e.is_past]
    recent = [e for e in all_events if e.is_past and e.event_date >= seven_days_ago]
    
    # Keep them in chronological order for the view
    upcoming.reverse() # asc

    return render_template("admin/events.html", unit=unit, events=upcoming, recent_events=recent)


# ── Archive Events ────────────────────────────────────────────────────────────

@admin.route("/unit/<unit_id>/archive")
@login_required
def archive(unit_id: str):
    """
    View the historical archive of past events.
    Events are grouped by Year -> Month to mirror standard interface structures.
    """
    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)
    
    all_events = Event.query.filter_by(unit_id=unit_id).order_by(Event.event_date.desc(), Event.event_time.desc()).all()
    past_events = [e for e in all_events if e.is_past]
    
    grouped = {}
    for e in past_events:
        year = e.event_date.year
        month = e.event_date.strftime("%b")
        if year not in grouped:
            grouped[year] = {}
        if month not in grouped[year]:
            grouped[year][month] = []
        grouped[year][month].append(e)
        
    return render_template("admin/archive.html", unit=unit, grouped=grouped)


@admin.route("/unit/<unit_id>/events/create", methods=["GET", "POST"])
@login_required
def create_event(unit_id: str):
    """
    Create a new event within the unit workspace.
    Accepts date, time, end time, location, and a response due date deadline.
    """
    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        event_date_str = request.form.get("event_date", "")
        event_time_str = request.form.get("event_time", "")
        event_end_time_str = request.form.get("event_end_time", "")
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        due_str = request.form.get("response_due_date", "")

        try:
            event_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid event date.", "danger")
            return render_template("admin/create_event.html", unit=unit)

        event_time = None
        if event_time_str:
            try:
                event_time = datetime.strptime(event_time_str, "%H:%M").time()
            except ValueError:
                pass

        event_end_time = None
        if event_end_time_str:
            try:
                event_end_time = datetime.strptime(event_end_time_str, "%H:%M").time()
            except ValueError:
                pass

        response_due = None
        if due_str:
            try:
                response_due = datetime.strptime(due_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                pass

        # Validation: RSVP deadline must be before the event starts
        if response_due:
            event_start = datetime.combine(event_date, event_time or datetime.min.time())
            if response_due > event_start:
                flash("RSVP deadline cannot be after the event start time.", "danger")
                return render_template("admin/create_event.html", unit=unit)

        event = Event(
            unit_id=unit_id,
            created_by=current_user.id,
            name=name,
            event_date=event_date,
            event_time=event_time,
            event_end_time=event_end_time,
            location=location,
            description=description,
            response_due_date=response_due,
        )
        db.session.add(event)
        db.session.commit()
        
        # Send push notifications to all unit members
        try:
            send_new_event_notification(event)
        except Exception as e:
            current_app.logger.error(f"Error sending event notifications: {e}")
            
        flash(f"Event '{name}' created.", "success")
        return redirect(url_for("admin.events", unit_id=unit_id))

    return render_template("admin/create_event.html", unit=unit)


# ── Edit Event ────────────────────────────────────────────────────────────────

@admin.route("/unit/<unit_id>/events/<event_id>/edit", methods=["GET", "POST"])
@login_required
def edit_event(unit_id: str, event_id: str):
    """
    Modify an existing event.
    Updating the event_date, event_end_time, or response_due_date will instantly
    impact visibility across member dashboards and archives.
    """
    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)
    event = db.get_or_404(Event, event_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        event_date_str = request.form.get("event_date", "")
        event_time_str = request.form.get("event_time", "")
        event_end_time_str = request.form.get("event_end_time", "")
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        due_str = request.form.get("response_due_date", "")

        try:
            event_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid event date.", "danger")
            return render_template("admin/edit_event.html", unit=unit, event=event)

        event_time = None
        if event_time_str:
            try:
                event_time = datetime.strptime(event_time_str, "%H:%M").time()
            except ValueError:
                pass

        event_end_time = None
        if event_end_time_str:
            try:
                event_end_time = datetime.strptime(event_end_time_str, "%H:%M").time()
            except ValueError:
                pass

        response_due = None
        if due_str:
            try:
                response_due = datetime.strptime(due_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                pass

        # Validation: RSVP deadline must be before the event starts
        if response_due:
            event_start = datetime.combine(event_date, event_time or datetime.min.time())
            if response_due > event_start:
                flash("RSVP deadline cannot be after the event start time.", "danger")
                return render_template("admin/edit_event.html", unit=unit, event=event)

        event.name = name
        event.event_date = event_date
        event.event_time = event_time
        event.event_end_time = event_end_time
        event.location = location
        event.description = description
        event.response_due_date = response_due
        db.session.commit()

        flash(f"Event '{name}' updated.", "success")
        return redirect(url_for("admin.unit_detail", unit_id=unit_id))

    return render_template("admin/edit_event.html", unit=unit, event=event)


# ── Delete Event ──────────────────────────────────────────────────────────────

@admin.route("/unit/<unit_id>/events/<event_id>/delete", methods=["POST"])
@login_required
def delete_event(unit_id: str, event_id: str):
    """
    Permanently delete an event from the unit.
    This action is irreversible and cascades to delete all associated RSVPs and attendance records.
    """
    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)
    event = db.get_or_404(Event, event_id)

    db.session.delete(event)
    db.session.commit()

    flash(f"Event '{event.name}' was successfully deleted.", "success")
    return redirect(url_for("admin.events", unit_id=unit_id))


# ── Muster Roll ───────────────────────────────────────────────────────────────

@admin.route("/unit/<unit_id>/events/<event_id>/muster")
@login_required
def muster_roll(unit_id: str, event_id: str):
    """
    Display the Attendance Sheet for an event.
    Admins can see who RSVP'd and mark actual attendance.
    """
    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)
    event = db.get_or_404(Event, event_id)

    members = UnitMember.query.filter_by(unit_id=unit_id, approved=True).all()
    responses = {r.user_id: r for r in EventResponse.query.filter_by(event_id=event_id).all()}
    records = {r.user_id: r for r in AttendanceRecord.query.filter_by(event_id=event_id).all()}

    # Calculate 'effective' attendance for each member to show in the UI as defaults
    effective_status = {}
    for m in members:
        rec = records.get(m.user_id)
        resp = responses.get(m.user_id)
        
        if rec:
            # Official record always wins
            effective_status[m.user_id] = "present" if rec.was_present else "absent"
        elif resp and resp.status == "attending":
            # Default to present if they RSVP'd attending
            effective_status[m.user_id] = "auto_present"
        else:
            # Everyone else defaults to absent
            effective_status[m.user_id] = "auto_absent"

    return render_template(
        "admin/muster_roll.html",
        unit=unit,
        event=event,
        members=members,
        responses=responses,
        records=records,
        effective_status=effective_status,
    )


@admin.route("/unit/<unit_id>/events/<event_id>/mark-attendance", methods=["POST"])
@login_required
def mark_attendance(unit_id: str, event_id: str):
    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)
    event = db.get_or_404(Event, event_id)

    user_id = request.form.get("user_id")
    was_present = request.form.get("was_present") == "true"

    record = AttendanceRecord.query.filter_by(event_id=event_id, user_id=user_id).first()
    if record:
        record.was_present = was_present
        record.marked_by = current_user.id
    else:
        record = AttendanceRecord(
            event_id=event_id,
            user_id=user_id,
            marked_by=current_user.id,
            was_present=was_present,
        )
        db.session.add(record)

    db.session.commit()
    return redirect(url_for("admin.muster_roll", unit_id=unit_id, event_id=event_id))


# ── Members ───────────────────────────────────────────────────────────────────

@admin.route("/unit/<unit_id>/members")
@login_required
def members(unit_id: str):
    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)
    memberships = UnitMember.query.filter_by(unit_id=unit_id).all()
    return render_template("admin/members.html", unit=unit, memberships=memberships)


# ── Unit Settings ─────────────────────────────────────────────────────────────

@admin.route("/unit/<unit_id>/settings", methods=["GET", "POST"])
@login_required
def unit_settings(unit_id: str):
    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)

    if request.method == "POST":
        unit.name = request.form.get("name", unit.name).strip()
        unit.city = request.form.get("city", unit.city).strip()
        unit.province = request.form.get("province", unit.province).strip()
        unit.description = request.form.get("description", unit.description).strip()
        unit.twilio_account_sid = request.form.get("twilio_account_sid", "").strip() or None
        unit.twilio_auth_token = request.form.get("twilio_auth_token", "").strip() or None
        unit.twilio_phone_number = request.form.get("twilio_phone_number", "").strip() or None
        unit.time_format = request.form.get("time_format", "12h")
        db.session.commit()
        flash("Organization settings saved.", "success")

    return render_template("admin/settings.html", unit=unit)


@admin.route("/unit/<unit_id>/delete", methods=["POST"])
@login_required
def delete_unit(unit_id: str):
    """Permanently delete an organization and all its data."""
    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)

    # Cascading deletion is handled at the model level (Unit.members, Unit.events, etc.)
    db.session.delete(unit)
    db.session.commit()

    flash(f"Organization '{unit.name}' has been permanently deleted.", "success")
    return redirect(url_for('member.dashboard'))


@admin.route("/unit/<unit_id>/reminders/send", methods=["POST"])
@login_required
def trigger_reminders(unit_id: str):
    """Manually trigger RSVP reminders for upcoming events in this unit."""
    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)
    
    count = send_deadline_reminders(unit_id=unit.id, force=True)
    if count > 0:
        flash(f"Sent {count} push notification reminder(s).", "success")
    else:
        flash("No pending RSVPs found for upcoming events.", "info")
        
    return redirect(url_for("admin.unit_detail", unit_id=unit_id))


# ── Export ────────────────────────────────────────────────────────────────────

@admin.route("/unit/<unit_id>/export")
@login_required
def export_attendance(unit_id: str):
    """Export attendance records as a CSV download."""
    import csv
    import io
    from flask import make_response

    unit = db.get_or_404(Unit, unit_id)
    _require_admin(unit)

    memberships = UnitMember.query.filter_by(unit_id=unit_id, approved=True).all()
    events = Event.query.filter_by(unit_id=unit_id).order_by(Event.event_date).all()

    output = io.StringIO()
    writer = csv.writer(output)

    header = ["Last Name", "First Name", "Title", "Reference ID"] + [e.name for e in events] + ["Attendance %"]
    writer.writerow(header)

    for m in memberships:
        user = m.user
        records = {r.event_id: r for r in AttendanceRecord.query.filter_by(user_id=user.id).all()}
        row = [user.last_name, user.first_name, user.title or "", user.reference_id or ""]
        present_count = 0
        for event in events:
            rec = records.get(event.id)
            if rec:
                row.append("P" if rec.was_present else "A")
                if rec.was_present:
                    present_count += 1
            else:
                row.append("-")
        pct = f"{round(present_count / len(events) * 100)}%" if events else "N/A"
        row.append(pct)
        writer.writerow(row)

    output.seek(0)
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=attendance_{unit.name}.csv"
    response.headers["Content-Type"] = "text/csv"
    return response
