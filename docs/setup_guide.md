# Panduan Setup Lokal MTOA ALR

Panduan ini buat laptop developer (Windows, PowerShell). Untuk server production, lihat [deploy.md](deploy.md).

## 1. Python & library

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` = library aplikasi (`requirements.txt`) + alat test (pytest). Server production cukup `requirements.txt`.
Versi library dikunci persis. Jangan `pip install` paket lain di venv ini tanpa ikut mengunci versinya.

## 2. File `.env`

```powershell
Copy-Item .env.example .env
```

Isi **tiga** nilai wajib berikut. Aplikasi menolak jalan kalau salah satunya kosong.

| Isian | Cara bikin |
|---|---|
| `SECRET_KEY` | `.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"` |
| `ENCRYPTION_KEY` | `.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DATABASE_URL` | `postgresql+psycopg://USER:PASSWORD@localhost:5432/NAMA_DB` |

`ENCRYPTION_KEY` dipakai untuk mengenkripsi access note. **Jangan diganti** setelah ada data: access note lama tidak akan bisa dibuka lagi.
Isian lain boleh dibiarkan sesuai `.env.example` untuk development (OTP dicetak ke terminal, rate limit di memori).

## 3. Database (PostgreSQL)

```powershell
createdb -U postgres db_mtoa_alr
.\.venv\Scripts\python.exe -m flask --app run db upgrade
.\.venv\Scripts\python.exe -m flask --app run seed-categories
.\.venv\Scripts\python.exe -m flask --app run create-admin
```

## 4. Menjalankan aplikasi

Butuh **dua terminal**:

```powershell
# terminal 1: web
.\.venv\Scripts\python.exe -m flask --app run run

# terminal 2: worker pemeriksaan link (tombol "Cek Semua" di Link Monitoring cuma ngantrekan, worker ini yg ngerjain)
.\.venv\Scripts\python.exe -m flask --app run monitor-worker
```

Buka http://127.0.0.1:5000. Cek kesehatan:
- http://127.0.0.1:5000/health: proses web hidup
- http://127.0.0.1:5000/health/ready: database, penyimpanan rate limit, dan folder lampiran siap

Kode OTP login muncul di terminal 1 (mode `OTP_DELIVERY_MODE=console`).

## 5. Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q
# komponen React (butuh Node.js 24, cuma kalau ngubah frontend/)
cd frontend; npm ci; npm test
```

## Catatan
- Gunakan `python -m pip` dan `python -m flask`, bukan `pip`/`flask` langsung (lebih aman di Windows).
- File `.env` berisi data rahasia dan tidak boleh di-commit.
- Dokumentasi requirement: `docs/requirements.md`. Frontend React: `docs/frontend-react.md`.
