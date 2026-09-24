# Panduan Setup Lokal MTOA ALR

## Menjalankan di lokal (PowerShell)
1. `python -m venv .venv`
2. `.\.venv\Scripts\Activate.ps1`
3. `python -m pip install -r requirements.txt`
4. `Copy-Item .env.example .env`, lalu isi `SECRET_KEY` dan `DATABASE_URL`
5. Generate SECRET_KEY: `python -c "import secrets; print(secrets.token_hex(32))"`
6. `python run.py`, lalu buka http://127.0.0.1:5000/health

## Tes
`python -m pytest -v`

## Catatan
- Gunakan `python -m pip`, bukan `pip` langsung (lebih aman di Windows).
- File `.env` berisi data rahasia dan tidak boleh di-commit.

Dokumentasi requirement: `docs/requirements.md`