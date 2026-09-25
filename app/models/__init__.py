"""Kumpulan model ORM; semua model diimpor di sini agar terdeteksi oleh Flask-Migrate."""
from app.models.audit_log import AuditLog
from app.models.category import Category
from app.models.otp_code import OtpCode
from app.models.user import User
from app.models.user_preference import UserPreference

# Daftar model yang boleh diimpor dari luar: from app.models import User
__all__ = ["AuditLog", "Category", "OtpCode", "User", "UserPreference"]