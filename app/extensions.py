"""Objek extension Flask yang dibuat SEKALI dan di-import ulang oleh modul lain (prinsip DRY)."""

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import MetaData

# --- Aturan penamaan constraint database agar konsisten & mudah dilacak di migrasi ---
NAMING_CONVENTION_DICT = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Objek ORM database; dipakai oleh semua model di folder models/
db = SQLAlchemy(metadata=MetaData(naming_convention=NAMING_CONVENTION_DICT))

# Pengelola migrasi skema database (flask db migrate / upgrade)
migrate = Migrate()

# Proteksi CSRF global untuk semua form POST
csrf = CSRFProtect()