"""Form bikin & edit group."""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional
from app.utils.constants import MAX_GROUP_DESCRIPTION_LENGTH, MAX_GROUP_NAME_LENGTH

class GroupForm(FlaskForm):
    """Nama wajib, deskripsi opsional."""
    name = StringField("Group Name", validators=[
        DataRequired(message="Group name is required"),
        Length(max=MAX_GROUP_NAME_LENGTH),
    ])
    description = TextAreaField("Description", validators=[Optional(), Length(max=MAX_GROUP_DESCRIPTION_LENGTH)])