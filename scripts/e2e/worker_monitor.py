"""Worker uji skenario monitor: sama kayak `flask monitor-worker`, tapi pemeriksaan jaringan diganti nunggu 1 detik
per link (link ke-4, 8, ... dianggap tidak aktif). Database-nya sama dgn server uji (E2E_DB_PATH)."""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config import TestingConfig  # noqa: E402

TestingConfig.SQLALCHEMY_DATABASE_URI = f"sqlite:///{Path(os.environ['E2E_DB_PATH']).as_posix()}"

from app import create_app  # noqa: E402
from app.services import link_check_service, link_monitor_service  # noqa: E402
from app.services.link_check_service import LinkCheckResult  # noqa: E402


def fake_check(target, **kwargs):
    time.sleep(1)
    return LinkCheckResult("up" if target.entry_id % 4 else "down", "uji")


link_check_service.check_target = fake_check
app = create_app("testing")
with app.app_context():
    while True:
        link_monitor_service.process_pending_monitor()
        time.sleep(1)
