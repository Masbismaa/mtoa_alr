"""Objek extension Flask yang dibuat SEKALI dan di-import ulang oleh modul lain (prinsip DRY)."""
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

# Objek ORM database; dipakai oleh semua model di folder models/
db = SQLAlchemy()

# Pengelola migrasi skema database (flask db migrate / upgrade)
migrate = Migrate()

# Proteksi CSRF global untuk semua form POST
csrf = CSRFProtect()