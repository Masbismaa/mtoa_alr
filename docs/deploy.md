# Deploy ALR di Server Linux

Langkah ini dijalankan di terminal server (misalnya lewat MobaXterm / SSH). Contoh perintah untuk Ubuntu/Debian.
Ganti `/opt/alr` dan user `alr` kalau lokasinya beda.

## Yang dibutuhkan server

| Layanan | Kenapa wajib |
|---|---|
| Python 3.13 + venv | menjalankan aplikasi |
| PostgreSQL + `postgresql-client` | database; `pg_dump`/`pg_restore` dipakai fitur backup |
| Redis | rate limit & blokir salah login dibagi ke semua proses gunicorn (aplikasi menolak start tanpa ini) |
| nginx + sertifikat HTTPS | cookie login production cuma dikirim lewat HTTPS. Lewat `http://` login **tidak akan bisa** |

```bash
# Ubuntu 22.04 bawaannya Python 3.10, versi 3.13 dari PPA deadsnakes (dipasang di samping, python3 sistem ga berubah)
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt install python3.13 python3.13-venv postgresql-client redis-server nginx
sudo systemctl enable --now redis-server
```

Redis cukup dengar di `127.0.0.1`, jangan dibuka ke jaringan.

## 1. Kode & library

```bash
sudo useradd --system --home /opt/alr alr
sudo git clone <url-repo> /opt/alr && sudo chown -R alr: /opt/alr
cd /opt/alr
sudo -u alr python3.13 -m venv .venv
sudo -u alr .venv/bin/pip install -r requirements.txt
```

## 2. File `.env`

Salin `.env.example` ke `.env`, lalu isi minimal:

```ini
APP_ENV=production
# server uji coba: label TEST tampil di layar biar ga ketuker sama production
APP_ENV_LABEL=TEST
SECRET_KEY=<generate baru, jangan pakai punya laptop>
ENCRYPTION_KEY=<generate baru; simpan juga di tempat aman, backup tanpa kunci ini tidak bisa dibaca>
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/db_ict_alr
OTP_DELIVERY_MODE=smtp
SMTP_HOST=intramail.dnsalias.com
SMTP_PORT=465
SMTP_SECURITY=ssl
SMTP_FROM=...
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_CERT_SHA256=...
RATELIMIT_STORAGE_URI=redis://127.0.0.1:6379/0
# di belakang nginx (1 proxy)
TRUSTED_PROXY_COUNT=1
```

```bash
sudo chmod 600 /opt/alr/.env && sudo chown alr: /opt/alr/.env
```

## 3. Database & admin pertama

```bash
cd /opt/alr
sudo -u alr .venv/bin/flask --app run db upgrade
sudo -u alr .venv/bin/flask --app run seed-categories
sudo -u alr .venv/bin/flask --app run create-admin
```

## 4. Service web & worker (systemd)

`/etc/systemd/system/alr-web.service`:

```ini
[Unit]
Description=ALR web
After=network.target postgresql.service redis-server.service

[Service]
User=alr
WorkingDirectory=/opt/alr
# port 8010: 8000 di server uji sudah dipakai Docker. timeout 300 dtk: backup & restore database jalan di dalam request
ExecStart=/opt/alr/.venv/bin/gunicorn --bind 127.0.0.1:8010 --workers 3 --timeout 300 run:app
Restart=always

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/alr-monitor.service` (worker cek link, tombol "Cek Semua" cuma mengantrekan):

```ini
[Unit]
Description=ALR link monitor worker
After=network.target postgresql.service

[Service]
User=alr
WorkingDirectory=/opt/alr
ExecStart=/opt/alr/.venv/bin/flask --app run monitor-worker
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now alr-web alr-monitor
curl -s http://127.0.0.1:8010/health/ready   # semua harus "ok"
```

## 5. nginx (HTTPS)

`/etc/nginx/sites-available/alr`:

```nginx
server {
    listen 443 ssl;
    server_name alr.contoh.local;
    ssl_certificate     /etc/ssl/alr/alr.crt;
    ssl_certificate_key /etc/ssl/alr/alr.key;
    # samakan dengan MAX_CONTENT_LENGTH aplikasi (5 lampiran x 10 MB)
    client_max_body_size 55m;

    location / {
        proxy_pass http://127.0.0.1:8010;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 300s;
    }
}
server {
    listen 80;
    server_name alr.contoh.local;
    return 301 https://$host$request_uri;
}
```

```bash
sudo ln -s /etc/nginx/sites-available/alr /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## Update versi baru

```bash
cd /opt/alr
sudo -u alr .venv/bin/flask --app run backup --only database
sudo -u alr git pull
sudo -u alr .venv/bin/pip install -r requirements.txt
sudo -u alr .venv/bin/flask --app run db upgrade
sudo systemctl restart alr-web alr-monitor
```

## Kalau ada masalah

```bash
sudo journalctl -u alr-web -n 100      # log aplikasi
sudo journalctl -u alr-monitor -n 100  # log worker
curl -s http://127.0.0.1:8010/health/ready
```
