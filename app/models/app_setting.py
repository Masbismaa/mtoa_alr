"""Pengaturan aplikasi yg berlaku buat semua proses (web, worker, CLI), disimpen per key."""
from app.extensions import db
from app.models.base_model import TimestampMixin


class AppSetting(TimestampMixin, db.Model):
    __tablename__ = "app_settings"
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text, nullable=False)
