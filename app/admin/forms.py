"""
admin/forms.py — WTForms definitions for the admin blueprint.
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class CreateUnitForm(FlaskForm):
    """
    Form for creating a new organization.
    Used in Phase 3 when a new user registers and wants to set up an organization.
    """
    name = StringField(
        "Organization Name",
        validators=[
            DataRequired(message="Organization name is required."),
            Length(max=200, message="Name is too long."),
        ],
        description="e.g. City Club or Local Chapter"
    )



    description = TextAreaField("Description", validators=[Optional()])

    submit = SubmitField("Create Organization")
