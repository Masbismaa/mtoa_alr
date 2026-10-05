"""Form pengaturan Link Monitoring admin."""
from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField
from wtforms.validators import DataRequired, NumberRange

from app.utils.constants import LINK_MONITOR_MAX_INTERVAL_MINUTES, LINK_MONITOR_MIN_INTERVAL_MINUTES


class LinkMonitorSettingsForm(FlaskForm):
    is_enabled = BooleanField("Aktifkan pemeriksaan otomatis")
    interval_minutes = IntegerField(
        "Interval pemeriksaan (menit)",
        validators=[
            DataRequired(message="Interval wajib diisi"),
            NumberRange(
                min=LINK_MONITOR_MIN_INTERVAL_MINUTES,
                max=LINK_MONITOR_MAX_INTERVAL_MINUTES,
                message=f"Interval harus {LINK_MONITOR_MIN_INTERVAL_MINUTES}-{LINK_MONITOR_MAX_INTERVAL_MINUTES} menit",
            ),
        ],
    )
