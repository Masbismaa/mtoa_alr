# Access Link Register

Aplikasi Flask untuk mencatat link, alamat, kredensial akses, lampiran, kategori, dan group kerja ICT. Aplikasi memakai autentikasi password dan OTP, serta menyediakan audit log dan export Excel.

## Menjalankan aplikasi

1. Buat virtual environment dan pasang dependency.

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. Salin `.env.example` menjadi `.env`, lalu isi `SECRET_KEY`, `DATABASE_URL`, dan `ENCRYPTION_KEY`.

3. Terapkan migration dan seed kategori.

   ```powershell
   .\.venv\Scripts\python.exe -m flask --app run db upgrade
   .\.venv\Scripts\python.exe -m flask --app run seed-categories
   ```

4. Jalankan aplikasi lokal.

   ```powershell
   .\.venv\Scripts\python.exe -m flask --app run run
   ```

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Perintah CLI

```powershell
.\.venv\Scripts\python.exe -m flask --app run create-admin
.\.venv\Scripts\python.exe -m flask --app run set-admin
.\.venv\Scripts\python.exe -m flask --app run unset-admin
.\.venv\Scripts\python.exe -m flask --app run check-links
```

`check-links` dipanggil oleh Task Scheduler atau cron untuk menjalankan pemeriksaan status link otomatis sesuai interval yang diatur admin.

## Deploy

Gunakan server WSGI dan HTTPS untuk production. Set `APP_ENV=production`, gunakan penyimpanan rate limit bersama seperti Redis, dan konfigurasi pengiriman OTP production sebelum aplikasi dibuka untuk pengguna.
