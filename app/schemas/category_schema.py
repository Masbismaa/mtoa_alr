"""Form tambah & edit kategori."""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional
from app.utils.constants import MAX_CATEGORY_DESCRIPTION_LENGTH, MAX_CATEGORY_NAME_LENGTH

class CategoryForm(FlaskForm):
    """Nama wajib, deskripsi opsional."""
    name = StringField("Nama Kategori", validators=[
        DataRequired(message="Nama kategori wajib diisi"),
        Length(max=MAX_CATEGORY_NAME_LENGTH),
    ])
    description = TextAreaField("Deskripsi", validators=[Optional(), Length(max=MAX_CATEGORY_DESCRIPTION_LENGTH)])