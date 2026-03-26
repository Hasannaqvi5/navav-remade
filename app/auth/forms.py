"""
auth/forms.py — WTForms definitions for the authentication blueprint.

━━━ Why WTForms? ━━━
  WTForms handles three concerns in one place:
    1. Field validation (required fields, min length, email format, matching passwords)
    2. CSRF protection (Flask-WTF automatically adds a hidden token to every form
       that is verified on POST — prevents cross-site request forgery attacks)
    3. Clean Python objects (instead of raw request.form.get() calls in routes)

━━━ Forms in this file ━━━
  LoginForm         → /auth/login
  OpenRegisterForm  → /auth/register  (NEW — open sign-up, no invite needed)
  InviteRegisterForm→ /auth/register/invite  (existing invite-token flow)
  JoinOrgForm       → /auth/join/<token>  (shareable join link — just confirm name)
  ForgotPasswordForm→ /auth/forgot-password
  ResetPasswordForm → /auth/reset-password/<token>
"""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import (
    DataRequired,   # Field must be non-empty
    Email,          # Must be a syntactically valid email address
    EqualTo,        # Two fields must contain equal values (confirm password)
    Length,         # String must be within a character length range
    Optional,       # Field is not required (skips other validators if empty)
)


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginForm(FlaskForm):
    """
    Form for the /auth/login page.

    Only two required fields: email and password.
    The 'remember' checkbox tells Flask-Login to set a persistent cookie
    so the user stays logged in across browser restarts.
    """

    email = StringField(
        "Email Address",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Please enter a valid email address."),
        ],
    )

    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Password is required.")],
    )

    # Checking this extends the session cookie lifetime (Flask-Login remember_me)
    remember = BooleanField("Remember me")

    submit = SubmitField("Log In")


# ── Open Registration (Phase 3 — no invite needed) ────────────────────────────

class OpenRegisterForm(FlaskForm):
    """
    Form for the open /auth/register page.

    Anyone can register — they just need an email, name, and password.
    After registering they will be prompted to create or join an organisation.

    Note: the email uniqueness check is done in the route, not here, because
    WTForms validators run before the route has a chance to query the DB.
    """

    first_name = StringField(
        "First Name",
        validators=[
            DataRequired(message="First name is required."),
            Length(max=100, message="Name is too long."),
        ],
    )

    last_name = StringField(
        "Last Name",
        validators=[
            DataRequired(message="Last name is required."),
            Length(max=100),
        ],
    )

    email = StringField(
        "Email Address",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Please enter a valid email address."),
        ],
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8, message="Password must be at least 8 characters."),
        ],
    )

    # EqualTo('password') checks that this field's value exactly matches
    # the value in the 'password' field at validation time
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwords must match."),
        ],
    )

    submit = SubmitField("Create Account")


# ── Invite-based Registration (email-invite flow, kept for individual invites) ─

class InviteRegisterForm(FlaskForm):
    """
    Form for /auth/register/invite — completing an individual email invite.

    Email is NOT a field here because it comes from the Invite record
    (the admin pre-specified it) and should not be changeable by the registrant.
    The invite token is passed as a hidden field in the HTML template.
    """

    first_name = StringField(
        "First Name",
        validators=[DataRequired(), Length(max=100)],
    )

    last_name = StringField(
        "Last Name",
        validators=[DataRequired(), Length(max=100)],
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8, message="Password must be at least 8 characters."),
        ],
    )

    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )

    submit = SubmitField("Create Account")


# ── Join Organisation via shareable link ─────────────────────────────────────

class JoinOrgForm(FlaskForm):
    """
    Form shown at /auth/join/<join_token> when clicking a shared org link.

    If the visitor is already logged in, only the submit button is shown.
    If they're not logged in, they need to either log in or create an account
    first — the route handles that redirect logic.
    """
    # No fields needed — the join action just needs CSRF protection.
    # The join token comes from the URL <join_token> route parameter.
    submit = SubmitField("Join Organisation")


# ── Forgot Password ───────────────────────────────────────────────────────────

class ForgotPasswordForm(FlaskForm):
    """
    Form for /auth/forgot-password.
    User enters their email; if it matches an account, a reset link is sent.
    The route always shows the same flash message whether or not the email
    exists, to prevent leaking which emails are registered.
    """
    email  = StringField("Email Address", validators=[DataRequired(), Email()])
    submit = SubmitField("Send Reset Link")


# ── Reset Password ────────────────────────────────────────────────────────────

class ResetPasswordForm(FlaskForm):
    """
    Form for /auth/reset-password/<token>.
    The token in the URL is verified by the route before this form is shown.
    """
    password = PasswordField(
        "New Password",
        validators=[DataRequired(), Length(min=8, message="Password must be at least 8 characters.")],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Update Password")
