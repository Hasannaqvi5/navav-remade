from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.member import member
from app.extensions import db
from app.models.unit import Unit, UnitMember
from app.models.event import Event
from app.models.response import EventResponse, RESPONSE_ATTENDING, RESPONSE_NOT_ATTENDING, ABSENCE_REASONS
from app.models.attendance import AttendanceRecord
from datetime import datetime, timezone


def _get_membership(unit_id: str) -> UnitMember:
    """Return UnitMember for current_user in this unit or abort 403."""
    membership = UnitMember.query.filter_by(user_id=current_user.id, unit_id=unit_id, approved=True).first()
    if not membership:
        abort(403)
    return membership


# ── Member Dashboard ──────────────────────────────────────────────────────────

@member.route("/dashboard")
@login_required
def dashboard():
    """
    Primary member view showing upcoming events across all joined organizations.
    Presents an at-a-glance RSVP status for each event.
    """
    memberships = UnitMember.query.filter_by(user_id=current_user.id, approved=True).all()
    units = [m.unit for m in memberships]

    # Collect upcoming events across all units
    unit_ids = [m.unit_id for m in memberships]
    all_events = Event.query.filter(Event.unit_id.in_(unit_ids)).order_by(Event.event_date.asc(), Event.event_time.asc()).all() if unit_ids else []
    upcoming = [e for e in all_events if not e.is_past][:10]

    # Gather existing responses for those events
    event_ids = [e.id for e in upcoming]
    responses = {}
    if event_ids:
        for r in EventResponse.query.filter(
            EventResponse.event_id.in_(event_ids),
            EventResponse.user_id == current_user.id
        ).all():
            responses[r.event_id] = r

    return render_template(
        "member/dashboard.html",
        units=units,
        upcoming=upcoming,
        responses=responses,
    )


# ── Archive Events ────────────────────────────────────────────────────────────

@member.route("/archive")
@login_required
def archive():
    """
    View the historical archive of past events across all joined organizations.
    Allows members to look back at events they've attended or missed.
    """
    memberships = UnitMember.query.filter_by(user_id=current_user.id, approved=True).all()
    unit_ids = [m.unit_id for m in memberships]
    
    all_events = Event.query.filter(Event.unit_id.in_(unit_ids)).order_by(Event.event_date.desc(), Event.event_time.desc()).all() if unit_ids else []
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
        
    return render_template("member/archive.html", grouped=grouped)


# ── Event Detail & Response ───────────────────────────────────────────────────

@member.route("/event/<event_id>", methods=["GET", "POST"])
@login_required
def event_detail(event_id: str):
    """
    View event details and submit an RSVP (Attending/Not Attending/Reason).
    Enforces response due dates.
    """
    event = db.get_or_404(Event, event_id)
    _get_membership(event.unit_id)  # Ensure member belongs to the unit

    existing = EventResponse.query.filter_by(event_id=event_id, user_id=current_user.id).first()

    if request.method == "POST":
        if event.is_past_deadline:
            flash("The RSVP deadline for this event has passed. You can no longer change your response.", "danger")
            return redirect(url_for("member.event_detail", event_id=event_id))

        status = request.form.get("status")
        absence_reason = request.form.get("absence_reason") if status == RESPONSE_NOT_ATTENDING else None
        comment = request.form.get("comment", "").strip()[:500]

        if status not in (RESPONSE_ATTENDING, RESPONSE_NOT_ATTENDING):
            flash("Invalid response.", "danger")
        else:
            if existing:
                existing.status = status
                existing.absence_reason = absence_reason
                existing.comment = comment
                existing.responded_at = datetime.now(timezone.utc)
            else:
                existing = EventResponse(
                    event_id=event_id,
                    user_id=current_user.id,
                    status=status,
                    absence_reason=absence_reason,
                    comment=comment,
                )
                db.session.add(existing)

            db.session.commit()
            flash("Your response has been saved.", "success")
            return redirect(url_for("member.event_detail", event_id=event_id))

    # ── Build attendee lists ───────────────────────────────────────────────
    # Get all members of this unit
    from app.models.user import User
    members = (
        db.session.query(User)
        .join(UnitMember, UnitMember.user_id == User.id)
        .filter(UnitMember.unit_id == event.unit_id, UnitMember.approved == True)
        .order_by(User.last_name, User.first_name)
        .all()
    )

    # Get all responses for this event
    all_responses = EventResponse.query.filter_by(event_id=event_id).all()
    response_map = {r.user_id: r.status for r in all_responses}

    attending = [u for u in members if response_map.get(u.id) == RESPONSE_ATTENDING]
    not_attending = [u for u in members if response_map.get(u.id) == RESPONSE_NOT_ATTENDING]
    no_response = [u for u in members if u.id not in response_map]

    return render_template(
        "member/event_detail.html",
        event=event,
        existing=existing,
        absence_reasons=ABSENCE_REASONS,
        ATTENDING=RESPONSE_ATTENDING,
        NOT_ATTENDING=RESPONSE_NOT_ATTENDING,
        attending=attending,
        not_attending=not_attending,
        no_response=no_response,
    )


# ── Profile ───────────────────────────────────────────────────────────────────

@member.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """
    Manage user profile information and notification preferences.
    Generic profile fields (Phone, Department, Specialty).
    """
    user = current_user

    if request.method == "POST":
        user.first_name = request.form.get("first_name", user.first_name).strip()
        user.last_name = request.form.get("last_name", user.last_name).strip()
        user.title = request.form.get("title", "").strip() or None
        user.reference_id = request.form.get("reference_id", "").strip() or None
        user.department = request.form.get("department", "").strip() or None
        user.specialty = request.form.get("specialty", "").strip() or None
        user.phone_number = request.form.get("phone_number", "").strip() or None
        user.notify_email = request.form.get("notify_email") == "on"
        user.notify_sms = request.form.get("notify_sms") == "on"

        joining_date_str = request.form.get("joining_date", "")
        if joining_date_str:
            try:
                from datetime import date
                user.joining_date = datetime.strptime(joining_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("member.profile"))

    return render_template("member/profile.html", user=user)


# ── Attendance History ────────────────────────────────────────────────────────

@member.route("/history")
@login_required
def history():
    """
    View strict attendance history calculation.
    If an administrator marks a user as present/absent, that record is used.
    If no record exists, past events default to the user's "Attending" RSVP status.
    """
    memberships = UnitMember.query.filter_by(user_id=current_user.id, approved=True).all()
    unit_ids = [m.unit_id for m in memberships]

    events = (
        Event.query.filter(Event.unit_id.in_(unit_ids))
        .order_by(Event.event_date.desc())
        .all()
    ) if unit_ids else []

    event_ids = [e.id for e in events]
    records = {}
    responses = {}
    if event_ids:
        for r in AttendanceRecord.query.filter(
            AttendanceRecord.event_id.in_(event_ids),
            AttendanceRecord.user_id == current_user.id
        ).all():
            records[r.event_id] = r
        for r in EventResponse.query.filter(
            EventResponse.event_id.in_(event_ids),
            EventResponse.user_id == current_user.id
        ).all():
            responses[r.event_id] = r

    present = 0
    total = 0
    for e in events:
        rec = records.get(e.id)
        if rec or e.is_past:
            total += 1
            if rec:
                if rec.was_present:
                    present += 1
            else:
                resp = responses.get(e.id)
                if resp and resp.status == RESPONSE_ATTENDING:
                    present += 1

    percentage = round(present / total * 100) if total else None

    return render_template(
        "member/history.html",
        events=events,
        records=records,
        responses=responses,
        present=present,
        total=total,
        percentage=percentage,
    )
