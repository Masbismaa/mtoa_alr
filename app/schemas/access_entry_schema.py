"""Form data link. Validasi dasar di sini, aturan per kategori & duplikat di access_entry_service."""

from flask_wtf import FlaskForm
from wtforms import RadioField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from app.utils.constants import (
    MAX_ACCESS_NOTE_LENGTH,
    MAX_ADDRESS_LENGTH,
    MAX_TEXT_LENGTH,
    MAX_TITLE_LENGTH,
    MAX_URL_LENGTH,
    MAX_USERNAME_LENGTH,
    VISIBILITY_PRIVATE,
    VISIBILITY_PUBLIC,
)

class AccessEntryForm(FlaskForm):
    """Form tambah/edit data link. Pilihan kategori diisi dari route."""
    category_id = SelectField("Category", coerce=int, validators=[DataRequired(message="Category is required")])
    title = StringField("Title", validators=[DataRequired(message="Title is required"), Length(max=MAX_TITLE_LENGTH)])
    url = StringField("URL", validators=[Optional(), Length(max=MAX_URL_LENGTH)])
    address = StringField("Address", validators=[Optional(), Length(max=MAX_ADDRESS_LENGTH)])
    # sengaja StringField, dicek angkanya di service biar pesannya bisa diatur sendiri
    port = StringField("Port", validators=[Optional(), Length(max=5)])
    username = StringField("Username", validators=[Optional(), Length(max=MAX_USERNAME_LENGTH)])
    access_note = TextAreaField("Access Note / Password", validators=[Optional(), Length(max=MAX_ACCESS_NOTE_LENGTH)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=MAX_TEXT_LENGTH)])
    visibility = RadioField(
        "Visibility",
        choices=[(VISIBILITY_PRIVATE, "Private"), (VISIBILITY_PUBLIC, "Public")],
        default=VISIBILITY_PRIVATE,
        validators=[DataRequired(message="Choose Public or Private")],
    )