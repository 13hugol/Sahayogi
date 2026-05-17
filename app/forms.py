from __future__ import annotations

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    EmailField,
    FloatField,
    IntegerField,
    PasswordField,
    RadioField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import Email, EqualTo, InputRequired, Length, NumberRange, Optional


class RegistrationForm(FlaskForm):
    full_name = StringField("Full name", validators=[InputRequired(), Length(max=120)])
    email = EmailField("Email", validators=[InputRequired(), Email(), Length(max=255)])
    location = StringField("Location", validators=[InputRequired(), Length(max=160)])
    password = PasswordField("Password", validators=[InputRequired(), Length(min=8, max=72)])
    confirm_password = PasswordField(
        "Confirm password",
        validators=[InputRequired(), EqualTo("password")],
    )
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[InputRequired(), Email()])
    password = PasswordField("Password", validators=[InputRequired()])
    submit = SubmitField("Log in")


class RequestResetForm(FlaskForm):
    email = EmailField("Email", validators=[InputRequired(), Email()])
    submit = SubmitField("Send reset link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New password", validators=[InputRequired(), Length(min=8, max=72)])
    confirm_password = PasswordField(
        "Confirm password",
        validators=[InputRequired(), EqualTo("password")],
    )
    submit = SubmitField("Reset password")


class ProfileForm(FlaskForm):
    username = StringField("Username", validators=[InputRequired(), Length(min=3, max=64)])
    headline = StringField("Headline", validators=[Optional(), Length(max=160)])
    bio = TextAreaField("Bio", validators=[Optional(), Length(max=1000)])
    location = StringField("Location", validators=[Optional(), Length(max=160)])
    city = StringField("City", validators=[Optional(), Length(max=80)])
    country = StringField("Country", validators=[Optional(), Length(max=80)])
    contact_email = EmailField("Public contact email", validators=[Optional(), Email(), Length(max=255)])
    latitude = FloatField("Latitude", validators=[Optional()])
    longitude = FloatField("Longitude", validators=[Optional()])
    avatar = FileField("Avatar", validators=[FileAllowed(["jpg", "jpeg", "png", "webp"])])
    offered_skills = SelectMultipleField("Skills offered", coerce=int)
    wanted_skills = SelectMultipleField("Skills wanted", coerce=int)
    submit = SubmitField("Save profile")


class ListingForm(FlaskForm):
    title = StringField("Title", validators=[InputRequired(), Length(max=140)])
    skill_id = SelectField("Skill", coerce=int, validators=[InputRequired()])
    category_id = SelectField("Category", coerce=int, validators=[InputRequired()])
    description = TextAreaField("Description", validators=[InputRequired(), Length(min=20, max=2500)])
    exchange_type = RadioField(
        "Exchange type",
        choices=[("teach", "Teach/Barter"), ("credit", "Credit")],
        validators=[InputRequired()],
        default="teach",
    )
    min_credits = IntegerField("Credit cost", validators=[Optional(), NumberRange(min=0, max=999)])
    location_text = StringField("Location text", validators=[Optional(), Length(max=160)])
    contact_method = StringField("Contact method", validators=[Optional(), Length(max=160)])
    availability_labels = TextAreaField(
        "Availability",
        description="One availability option per line, e.g. Mon evenings / Sat remote.",
        validators=[Optional(), Length(max=1000)],
    )
    submit = SubmitField("Save listing")


class CertificateForm(FlaskForm):
    skill_id = SelectField("Skill", coerce=int, validators=[InputRequired()])
    certificate = FileField(
        "Certificate file",
        validators=[InputRequired(), FileAllowed(["pdf", "png", "jpg", "jpeg"])],
    )
    submit = SubmitField("Upload certificate")


class ExchangeRequestForm(FlaskForm):
    offered_skill_id = SelectField("Skill you will barter", coerce=int, validators=[Optional()])
    requested_message = TextAreaField("Message", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Send request")


class MessageForm(FlaskForm):
    body = TextAreaField("Message", validators=[InputRequired(), Length(max=2000)])
    submit = SubmitField("Send")


class ReviewForm(FlaskForm):
    rating = SelectField(
        "Rating",
        coerce=int,
        choices=[(5, "5"), (4, "4"), (3, "3"), (2, "2"), (1, "1")],
        validators=[InputRequired()],
    )
    comment = TextAreaField("Comment", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Publish review")


class ReportForm(FlaskForm):
    reason = SelectField(
        "Reason",
        choices=[
            ("harassment", "Harassment"),
            ("fake_profile", "Fake profile"),
            ("fraud", "Fraud"),
            ("spam", "Spam"),
            ("other", "Other"),
        ],
        validators=[InputRequired()],
    )
    description = TextAreaField("Description", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Submit report")


class CategoryForm(FlaskForm):
    name = StringField("Category name", validators=[InputRequired(), Length(max=80)])
    slug = StringField("Slug", validators=[InputRequired(), Length(max=80)])
    description = StringField("Description", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Save category")


class SkillForm(FlaskForm):
    name = StringField("Skill name", validators=[InputRequired(), Length(max=80)])
    description = StringField("Description", validators=[Optional(), Length(max=255)])
    category_id = SelectField("Category", coerce=int, validators=[InputRequired()])
    submit = SubmitField("Save skill")


class SuspensionForm(FlaskForm):
    action = SelectField(
        "Action",
        choices=[("suspend", "Suspend"), ("ban", "Ban"), ("activate", "Re-activate")],
        validators=[InputRequired()],
    )
    days = IntegerField("Suspension days", validators=[Optional(), NumberRange(min=1, max=30)])
    reason = TextAreaField("Reason", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Update user")
