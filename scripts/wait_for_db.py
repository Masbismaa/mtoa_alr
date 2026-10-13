"""Tunggu PostgreSQL siap nerima koneksi (dipake job CI postgres_test sebelum migrasi). Gagal kalau lewat 60 detik."""
import os
import sys
import time

import psycopg

# URL SQLAlchemy (postgresql+psycopg://) diubah jadi URL biasa yg dimengerti psycopg
database_url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
for _ in range(30):
    try:
        psycopg.connect(database_url, connect_timeout=2).close()
        sys.exit(0)
    except psycopg.OperationalError:
        time.sleep(2)
sys.exit("Database tidak siap dalam 60 detik")
