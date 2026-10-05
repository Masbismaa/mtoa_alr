"""Model satu baris untuk pengaturan pemeriksaan status link otomatis."""
from app.extensions import db
from app.models.base_model import TimestampMixin
from app.utils.constants import (
    LINK_MONITOR_DEFAULT_INTERVAL_MINUTES,
    LINK_MONITOR_MAX_INTERVAL_MINUTES,
    LINK_MONITOR_MIN_INTERVAL_MINUTES,
    LINK_MONITOR_SETTING_ID,
)


class LinkMonitorSetting(TimestampMixin, db.Model):
    __tablename__ = "link_monitor_settings"

    id = db.Column(db.Integer, primary_key=True)
    is_enabled = db.Column(db.Boolean, nullable=False, default=True, server_default=db.text("true"))
    interval_minutes = db.Column(
        db.Integer, nullable=False, default=LINK_MONITOR_DEFAULT_INTERVAL_MINUTES,
        server_default=str(LINK_MONITOR_DEFAULT_INTERVAL_MINUTES),
    )
    last_run_at = db.Column(db.DateTime(timezone=True), nullable=True)
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = db.relationship("User")

    __table_args__ = (
        db.CheckConstraint(f"id = {LINK_MONITOR_SETTING_ID}", name="single_row"),
        db.CheckConstraint(
            f"interval_minutes BETWEEN {LINK_MONITOR_MIN_INTERVAL_MINUTES} AND {LINK_MONITOR_MAX_INTERVAL_MINUTES}",
            name="interval_valid",
        ),
    )
