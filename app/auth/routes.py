"""
auth/routes.py — Route handlers for the authentication blueprint.

━━━ Authentication flows in NavAv ━━━

  1. OPEN REGISTRATION  (/auth/register)
     Anyone can create an account with just email + name + password.
     After registering they are redirected to the main dashboard where they
     can create or join an organisation.

  2. INVITE-BASED REGISTRATION  (/auth/register/invite?token=...)
     Admin sends an individual invite to a specific email address.
     The link encodes the invite ID in an HMAC-signed token (itsdangerous).
     The token validates the email and pre-selects the role (admin/member).

  3. SHAREABLE JOIN LINK  (/auth/join/<join_token>)
     Admin copies a join URL from the unit settings page and shares it
     (e.g. in a group chat). Anyone with the link can join the unit.
     The join_token is a random DB-stored secret, not a signed JWT.

  4. LOGIN  (/auth/login)
  5. LOGOUT (/auth/logout)
  6. FORGOT / RESET PASSWORD  (/auth/forgot-password, /auth/reset-password/<token>)

━━━ Token types used ━━━
  - itsdangerous URLSafeTimedSerializer → individual invite tokens + password reset tokens
    (HMAC-signed, expire automatically after MAX_AGE seconds)
  - secrets.token_urlsafe → unit join tokens
    (random, stored in DB, invalidated by regenerating)
"""

from datetime import datetime, timezone
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from app.auth import auth
from app.auth.forms import (
    LoginForm,
    OpenRegisterForm,
    InviteRegisterForm,
    JoinOrgForm,
    ForgotPasswordForm,
    ResetPasswordForm,
)
from app.extensions import db
from app.models.user import User
from app.models.unit import Unit, UnitMember
from app.models.invite import Invite
from app.models.push_subscription import PushSubscription
from app.notifications.email import send_welcome_email


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_serializer() -> URLSafeTimedSerializer:
    """
    Return an itsdangerous serializer bound to the app's SECRET_KEY.

    Called fresh on each request so it always uses the current runtime key.
    The serializer both signs tokens (dumps) and verifies + decodes them (loads).
    Separate 'salt' strings prevent tokens from one flow being used in another
    (e.g. a password-reset token can't be submitted as an invite token).
    """
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


# ── Login ─────────────────────────────────────────────────────────────────────

@auth.route("/login", methods=["GET", "POST"])
def login():
    """
    Display and process the login form.

    GET  → render the form
    POST → validate email + password; on success set the session and redirect

    If the user already has a valid session cookie (is_authenticated is True)
    skip the form entirely — they don't need to log in again.
    """
    # Don't show the login form to someone who is already signed in
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = LoginForm()

    if form.validate_on_submit():
        # Normalise email: lowercase and strip leading/trailing whitespace
        # to prevent duplicate accounts caused by case or spacing differences
        email = form.email.data.strip().lower()

        # Look up the user by email — returns None if not found
        user = User.query.filter_by(email=email).first()

        # Three conditions must all be true for a successful login:
        #   1. A user with this email exists
        #   2. The account is not suspended (is_active)
        #   3. The submitted password matches the stored bcrypt hash
        if user and user.is_active and user.check_password(form.password.data):
            # Record the login timestamp (useful for admin dashboards)
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()

            # login_user() writes the user's ID into the session cookie.
            # remember=True extends the cookie beyond the browser session
            # (Flask-Login sets a "remember me" persistent cookie).
            login_user(user, remember=form.remember.data)

            # Flask-Login sets a `next` query param when redirecting to login
            # from a protected page. Honour it so users land where they intended.
            next_page = request.args.get("next")
            return redirect(next_page or url_for("index"))

        # Use a deliberately vague message — don't reveal which field was wrong
        # (avoids user enumeration attacks where attacker probes for valid emails)
        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html", form=form)


# ── Logout ────────────────────────────────────────────────────────────────────

@auth.route("/logout")
@login_required   # Flask-Login enforces this — guests get redirected to login
def logout():
    """
    Clear the user's session and redirect to the login page.
    logout_user() removes the user ID from the session cookie.
    """
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


# ── Open Registration (Phase 3) ───────────────────────────────────────────────

@auth.route("/register", methods=["GET", "POST"])
def register():
    """
    Open self-registration — anyone can sign up.

    GET  → show the registration form
    POST → validate, create User, log them in, redirect to dashboard

    After registration the user has an account but belongs to no unit yet.
    The dashboard will show a prompt to create or join an organisation.
    """
    # If they're already signed in, don't show the register page
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = OpenRegisterForm()

    if form.validate_on_submit():
        # Normalise email before storing
        email = form.email.data.strip().lower()

        # Extra server-side uniqueness check (WTForms can't query the DB)
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists. Try logging in.", "danger")
            return render_template("auth/register.html", form=form)

        # Create the new User record
        user = User(
            email=email,
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
        )
        # Hash the password with bcrypt via Werkzeug — never store plaintext
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        # Log the user in immediately after account creation
        login_user(user)
        send_welcome_email(user)
        flash("Welcome to NavAv! Create or join an organization to get started.", "success")
        return redirect(url_for("index"))

    return render_template("auth/register.html", form=form)


# ── Invite-based Registration (individual email invite) ───────────────────────

@auth.route("/register/invite", methods=["GET", "POST"])
def register_invite():
    """
    Invite-only registration via a signed email invite link.

    Flow:
      1. Admin creates an Invite record and a signed token is emailed to the recipient.
      2. Recipient clicks the link → lands here with ?token=<signed_id>
      3. Token is verified (signature + expiry via itsdangerous)
      4. Invite record is loaded and checked (not used, not expired)
      5. User fills out name + password and submits
      6. Account is created, Invite is marked as used, user is logged in

    The invite pre-specifies the email address and role — the registrant
    cannot change either of those.
    """
    # (We no longer block logged-in users immediately. We check the token first.)

    # The token is in the URL querystring on GET and in the hidden form field on POST
    token = request.args.get("token") or request.form.get("token")
    if not token:
        flash("A valid invite link is required to use this page.", "danger")
        return redirect(url_for("auth.login"))

    # ── Step 1: Verify the HMAC signature ─────────────────────────────────────
    # loads() raises SignatureExpired if the token is older than INVITE_TOKEN_MAX_AGE,
    # and BadSignature if the token was tampered with or is garbage.
    s = _get_serializer()
    try:
        invite_id = s.loads(
            token,
            max_age=current_app.config["INVITE_TOKEN_MAX_AGE"],
            salt="invite",   # Salt prevents cross-flow token reuse
        )
    except SignatureExpired:
        flash("This invite link has expired. Ask your unit admin for a new one.", "danger")
        return redirect(url_for("auth.login"))
    except BadSignature:
        flash("Invalid invite link.", "danger")
        return redirect(url_for("auth.login"))

    # ── Step 2: Load the Invite row and check it hasn't been used ──────────────
    invite = db.session.get(Invite, invite_id)
    if not invite or not invite.is_valid:
        flash("This invite link has already been used or is no longer valid.", "danger")
        return redirect(url_for("index") if current_user.is_authenticated else url_for("auth.login"))

    # ── Step 3: Handle already logged-in users ─────────────────────────────────
    if current_user.is_authenticated:
        if current_user.email.lower() != invite.email.lower():
            flash("This invite was sent to a different email address. Please log out first if you wish to accept it.", "warning")
            return redirect(url_for("index"))
        
        # User is logged in with the correct email, so accept the invite immediately
        # (Assuming they aren't already a member to prevent duplicate key errors)
        existing_membership = UnitMember.query.filter_by(user_id=current_user.id, unit_id=invite.unit_id).first()
        if not existing_membership:
            membership = UnitMember(user_id=current_user.id, unit_id=invite.unit_id, role=invite.role)
            db.session.add(membership)
            
        invite.is_used = True
        invite.accepted_at = datetime.now(timezone.utc)
        db.session.commit()
        flash("Invite accepted! You have successfully joined the organization.", "success")
        return redirect(url_for("index"))

    # ── Step 4: Handle an existing account that is NOT logged in ───────────────
    existing_user = User.query.filter_by(email=invite.email).first()
    if existing_user:
        flash("You already have an account! Please log in to accept your invite.", "info")
        # Pass the invite link as the 'next' parameter so they auto-accept after login
        return redirect(url_for("auth.login", next=url_for("auth.register_invite", token=token)))

    # ── Step 5: Show the registration form for brand new users ─────────────────
    form = InviteRegisterForm()

    if form.validate_on_submit():
        # ── Create the user ────────────────────────────────────────────────
        user = User(
            email=invite.email,       # Email comes from the invite, not the form
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
        )
        user.set_password(form.password.data)
        db.session.add(user)

        # flush() assigns user.id without committing so we can use it below
        db.session.flush()

        # ── Create the unit membership ─────────────────────────────────────
        membership = UnitMember(
            user_id=user.id,
            unit_id=invite.unit_id,
            role=invite.role,   # Role was pre-set by the admin when creating the invite
        )
        db.session.add(membership)

        # ── Mark the invite as consumed ────────────────────────────────────
        invite.is_used   = True
        invite.accepted_at = datetime.now(timezone.utc)
        db.session.commit()

        login_user(user)
        send_welcome_email(user)
        flash("Welcome! Your account has been created and you've joined the organization.", "success")
        return redirect(url_for("index"))

    return render_template("auth/register_invite.html", form=form, invite=invite, token=token)


# ── Shareable Join Link ───────────────────────────────────────────────────────

@auth.route("/join", methods=["GET", "POST"])
def join_prompt():
    """
    Allow users to manually paste a join code or full join URL.
    """
    if not current_user.is_authenticated:
        flash("Please log in or create an account to join an organisation.", "info")
        return redirect(url_for("auth.login", next=request.url))

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if not code:
            flash("Please enter a join code or link.", "danger")
            return redirect(url_for("auth.join_prompt"))
            
        # Extract token if they pasted a full URL
        token = code.split("/")[-1].split("?")[0]
        return redirect(url_for("auth.join_org", join_token=token))
        
    return render_template("auth/join_prompt.html")


@auth.route("/join/<join_token>", methods=["GET", "POST"])
def join_org(join_token: str):
    """
    Handle a shareable organisation join link.
    """
    # 1. Try resolving as a member join token
    unit = Unit.query.filter_by(join_token=join_token).first()
    role = "member"

    if unit and not unit.join_link_enabled:
        unit = None

    # 2. Try resolving as an admin join token
    if not unit:
        unit = Unit.query.filter_by(admin_join_token=join_token).first()
        role = "admin"
        if unit and not unit.admin_join_link_enabled:
            unit = None

    # Validate that the token exists AND the link is currently enabled
    if not unit:
        flash("This join link is invalid or has been disabled.", "danger")
        return redirect(url_for("index"))

    # If the visitor is not logged in, send them to login first.
    # Flask-Login's `next` mechanism will bring them back here after authentication.
    if not current_user.is_authenticated:
        flash("Please log in or create an account to join this organisation.", "info")
        return redirect(url_for("auth.login", next=request.url))

    form = JoinOrgForm()

    if form.validate_on_submit():
        # Check if the user is already a member of this unit
        existing = UnitMember.query.filter_by(
            user_id=current_user.id,
            unit_id=unit.id,
        ).first()

        if existing:
            # Already a member — just redirect to their dashboard
            flash(f"You are already a member of {unit.name}.", "info")
            return redirect(url_for("member.dashboard"))

        # Create a new membership with the appropriate role
        membership = UnitMember(
            user_id=current_user.id,
            unit_id=unit.id,
            role=role,
        )
        db.session.add(membership)
        db.session.commit()

        flash(f"You've joined {unit.name}! Welcome aboard.", "success")
        return redirect(url_for("member.dashboard"))

    return render_template("auth/join.html", form=form, unit=unit)


# ── Forgot Password ───────────────────────────────────────────────────────────

@auth.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """
    Request a password reset email.

    Security note: we ALWAYS flash the same message regardless of whether
    the submitted email is registered. This prevents user enumeration —
    an attacker cannot determine which emails have accounts by looking at
    different server responses.

    In Phase 9 the reset_url will be emailed via Flask-Mail.
    For now it is logged to the Flask dev console so you can copy it.
    """
    form = ForgotPasswordForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user  = User.query.filter_by(email=email).first()

        if user:
            # Sign the user's ID into a time-limited token.
            # salt="password-reset" prevents this token from being accepted
            # by the invite flow (even though both use the same SECRET_KEY).
            s     = _get_serializer()
            token = s.dumps(user.id, salt="password-reset")

            # _external=True generates a full absolute URL (including domain),
            # which is needed for links sent in emails.
            reset_url = url_for("auth.reset_password", token=token, _external=True)

            # DEV: log to console. Phase 9 will replace this with Flask-Mail.
            current_app.logger.info(f"[DEV] Password reset link for {email}: {reset_url}")

        # Always show this — don't reveal whether the email was found
        flash("If that email is registered, you'll receive a reset link shortly.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@auth.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    """
    Set a new password after clicking a signed reset link.

    The token is in the URL path (not a query param) so it is part of the
    page address — this makes it easy to bookmark or share by mistake, but
    itsdangerous makes it short-lived (RESET_TOKEN_MAX_AGE, default 1 hour)
    so it expires before becoming a security risk.
    """
    s = _get_serializer()
    try:
        user_id = s.loads(
            token,
            max_age=current_app.config["RESET_TOKEN_MAX_AGE"],
            salt="password-reset",
        )
    except (SignatureExpired, BadSignature):
        flash("This password reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()

    if form.validate_on_submit():
        # Hash and store the new password — never store plaintext
        user.set_password(form.password.data)
        db.session.commit()
        flash("Your password has been updated. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form, token=token)
    

# ── Push Notifications ────────────────────────────────────────────────────────

@auth.route("/push/subscription-public-key")
def get_vapid_public_key():
    """Returns the VAPID public key needed for the browser to subscribe."""
    return current_app.config.get("VAPID_PUBLIC_KEY", "")


@auth.route("/push/subscribe", methods=["POST"])
@login_required
def subscribe_push():
    """
    Receive a JSON subscription object from the browser and save it.
    The browser sends: { endpoint, keys: { p256dh, auth } }
    """
    from flask import current_app
    subscription_data = request.get_json(silent=True)
    
    if not subscription_data or "endpoint" not in subscription_data:
        return {"error": "Invalid subscription data: missing endpoint"}, 400

    # Extract keys
    keys = subscription_data.get("keys", {})
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")

    if not p256dh or not auth:
        return {"error": "Missing subscription keys"}, 400

    # Check if this exact subscription already exists for this user
    existing = PushSubscription.query.filter_by(
        user_id=current_user.id,
        endpoint=subscription_data["endpoint"]
    ).first()

    if not existing:
        new_sub = PushSubscription(
            user_id=current_user.id,
            endpoint=subscription_data["endpoint"],
            p256dh=p256dh,
            auth=auth,
            device_name=request.headers.get("User-Agent", "Unknown Device")
        )
        db.session.add(new_sub)
        db.session.commit()
        return {"status": "subscribed"}, 201

    return {"status": "already subscribed"}, 200
@auth.route("/push/unsubscribe", methods=["POST"])
@login_required
def unsubscribe_push():
    """
    Remove a push subscription from the database.
    The browser sends the endpoint URL to identify which subscription to remove.
    """
    subscription_data = request.get_json()
    if not subscription_data or "endpoint" not in subscription_data:
        return {"error": "Invalid request"}, 400

    PushSubscription.query.filter_by(
        user_id=current_user.id,
        endpoint=subscription_data["endpoint"]
    ).delete()
    
    db.session.commit()
    return {"status": "unsubscribed"}, 200
