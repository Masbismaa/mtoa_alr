"""Server Flask buat uji E2E (dinyalain otomatis sama skenario *.mjs di folder ini, ga perlu dijalanin manual).

python scripts/e2e/server.py <skenario>   skenario: table | auth | group | monitor
- database SQLite baru di E2E_DB_PATH (dibikin skenario di folder sementara), CSRF nyala kayak aslinya
- OTP selalu 123456, kecuali skenario auth (kode acak, dibaca skenario dari output email mode console)
- kalau udah siap nerima koneksi, nyetak 1 baris: SIAP {json info buat skenario}
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config import TestingConfig  # noqa: E402

SCENARIO = sys.argv[1] if len(sys.argv) > 1 else "table"
TestingConfig.SQLALCHEMY_DATABASE_URI = f"sqlite:///{Path(os.environ['E2E_DB_PATH']).as_posix()}"
TestingConfig.WTF_CSRF_ENABLED = True
TestingConfig.TESTING = False

from werkzeug.serving import run_simple  # noqa: E402
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import AccessEntry, Category  # noqa: E402
from app.services import auth_service, link_monitor_service  # noqa: E402
from app.services.group_service import add_group_entry, create_group  # noqa: E402
from app.services.seed_service import seed_default_categories  # noqa: E402
from app.utils.constants import ROLE_ADMIN  # noqa: E402

PASSWORD = "PasswordKuat123"

if SCENARIO != "auth":
    auth_service.generate_otp_code = lambda: "123456"
if SCENARIO == "monitor":
    # peringatan "worker kemungkinan tidak berjalan" dipercepat (aslinya 60 detik)
    link_monitor_service.MONITOR_WORKER_WAIT_WARNING_SECONDS = 4

app = create_app("testing")
app.config["UPLOAD_FOLDER"] = str(Path(os.environ["E2E_DB_PATH"]).parent / "uploads")


def add_entries(user, count, category, sub_category=None):
    """Link contoh: Portal (genap) / Router (ganjil), tiap ke-5 masuk sub-kategori, campuran public/private."""
    for index in range(count):
        db.session.add(AccessEntry(
            user_id=user.id, category_id=sub_category.id if sub_category and index % 5 == 0 else category.id,
            title=f"Portal {index:02d}" if index % 2 == 0 else f"Router {index:02d}",
            url=f"https://link{index:02d}.spindo.com", visibility="public" if index % 3 else "private",
        ))
    db.session.commit()


with app.app_context():
    db.create_all()
    seed_default_categories()
    web = db.session.execute(db.select(Category).filter_by(name="Web", parent_id=None)).scalar_one()
    info = {}
    if SCENARIO == "monitor":
        admin = auth_service.register_user("e2e.admin@spindo.com", PASSWORD, "Admin E2E", "ICT", "Manager", role=ROLE_ADMIN)
        add_entries(admin, 60, web)
    else:
        user = auth_service.register_user("e2e.user@spindo.com", PASSWORD, "User E2E", "ICT", "Staff")
        sub_category = Category(parent_id=web.id, name="SAP", is_active=True)
        db.session.add(sub_category)
        db.session.flush()
        add_entries(user, 25, web, sub_category)
        info["sub_category_id"] = sub_category.id
        if SCENARIO == "group":
            group = create_group(user, {"name": "Tim Besar"})
            for entry_id in db.session.scalars(db.select(AccessEntry.id).order_by(AccessEntry.id).limit(12)):
                add_group_entry(user, group, entry_id)
            info["group_id"] = group.id
    print("SIAP " + json.dumps(info), flush=True)

run_simple("127.0.0.1", 5077, app, threaded=True, use_reloader=False)
