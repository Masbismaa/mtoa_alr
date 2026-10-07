"""Model ORM untuk tabel user_preferences (SR-17 Theme Customizer & Dark Mode)."""

from app.extensions import db
from app.models.base_model import TimestampMixin
from app.utils.constants import (
    DEFAULT_ACCENT_COLOR,
    DEFAULT_FONT_FAMILY,
    THEME_MODE_LIGHT,
    THEME_MODE_LIST,
)
from app.utils.sql_helper import build_sql_in_list


class UserPreference(TimestampMixin, db.Model):
    """Preferensi tampilan per user; satu user hanya punya satu baris preferensi."""

    __tablename__ = "user_preferences"

    # --- Primary key & relasi ke users (unique = relasi 1-1) ---
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # --- Kolom preferensi tampilan ---
    theme_mode = db.Column(db.String(10), nullable=False, default=THEME_MODE_LIGHT, server_default=THEME_MODE_LIGHT)
    accent_color = db.Column(db.String(7), nullable=False, default=DEFAULT_ACCENT_COLOR, server_default=DEFAULT_ACCENT_COLOR)
    is_compact_view = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("false"))
    font_family = db.Column(db.String(30), nullable=False, default=DEFAULT_FONT_FAMILY, server_default=DEFAULT_FONT_FAMILY)
    # layout tabel ala ALV per tabel, misal {"entry": {"hidden_list": [...], "width_dict": {...}}}
    table_layout = db.Column(db.JSON, nullable=False, default=dict, server_default=db.text("'{}'"))

    # --- Relasi balik ke User ---
    user = db.relationship("User", back_populates="preference")

    # --- Constraint database: theme_mode hanya light atau dark ---
    __table_args__ = (
        db.CheckConstraint(f"theme_mode IN ({build_sql_in_list(THEME_MODE_LIST)})", name="theme_mode_valid"),
    )

    def __repr__(self):
        """Representasi singkat untuk debugging."""
        return f"<UserPreference user_id={self.user_id} theme={self.theme_mode}>"