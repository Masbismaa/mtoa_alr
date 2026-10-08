"""Satu antrean pemeriksaan manual bersama untuk seluruh proses aplikasi."""
from app.extensions import db


class LinkMonitorRun(db.Model):
    __tablename__ = "link_monitor_runs"
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(32), nullable=True)
    state = db.Column(db.String(16), nullable=False, default="idle", server_default="idle")
    processed_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    total_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    __table_args__ = (
        db.CheckConstraint("id = 1", name="single_monitor_run"),
        db.CheckConstraint("state IN ('idle','queued','running','completed','failed')", name="monitor_state_valid"),
    )
