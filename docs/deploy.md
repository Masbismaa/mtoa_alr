# Deploy ALR ke Server QAS (192.168.0.57)

Dijalankan di terminal server lewat MobaXterm (SSH). Polanya sama dengan aplikasi lain di server ini
(`ict-pgg-web`): kode di folder home user, Gunicorn lewat Unix socket, dijalankan `systemd`, diteruskan nginx.
Contoh di bawah pakai user `bisma` dan folder `/home/bisma/alr`.

## 1. Sekali di awal: Redis

Rate limit & blokir salah login dibagi ke semua proses Gunicorn lewat Redis (aplikasi menolak start tanpa ini).

```bash
sudo apt install -y redis-server python3.13-venv
sudo systemctl enable --now redis-server
redis-cli ping   # harus PONG
```

## 2. Ambil kode

Butuh deploy key server yg udah didaftarin di GitLab (Settings → Repository → Deploy keys, tanpa write access).

```bash
cd ~
git clone git@192.168.0.58:ict_group/ict-alr-web.git alr
cd ~/alr
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 3. File `.env`

Cuma buat pemasangan pertama. Setelah langkah 7, isinya ditimpa dari GitLab tiap deploy.

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Isi minimal:

```ini
APP_ENV=production
APP_ENV_LABEL=QAS
# QAS masih HTTP, jadi cookie login boleh lewat HTTP. Production (HTTPS) jangan isi baris ini
SESSION_COOKIE_SECURE=false
SECRET_KEY=<hasil: python3.13 -c "import secrets; print(secrets.token_hex(32))">
ENCRYPTION_KEY=<hasil: .venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
DATABASE_URL=postgresql+psycopg://alr_qas:PASSWORD@localhost:5432/db_alr_qas
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

## 4. Database & admin pertama

```bash
sudo -u postgres createuser --pwprompt alr_qas
sudo -u postgres createdb -O alr_qas db_alr_qas
cd ~/alr
.venv/bin/flask --app run db upgrade
.venv/bin/flask --app run seed-categories
.venv/bin/flask --app run create-admin
```

## 5. Service web & worker

`sudo nano /etc/systemd/system/alr.service`:

```ini
[Unit]
Description=Gunicorn ALR App (Python 3.13 venv)
After=network.target postgresql.service redis-server.service

[Service]
User=bisma
Group=www-data
WorkingDirectory=/home/bisma/alr
Environment="PATH=/home/bisma/alr/.venv/bin"
EnvironmentFile=/home/bisma/alr/.env
RuntimeDirectory=alr
RuntimeDirectoryMode=0755
RuntimeDirectoryPreserve=yes
# timeout 300 dtk: backup & restore database jalan di dalam request
ExecStart=/home/bisma/alr/.venv/bin/gunicorn -w 3 --timeout 300 -b 0.0.0.0:8010 run:app
Umask=007
Restart=always
RestartSec=3
ExecReload=/bin/kill -s HUP $MAINPID

[Install]
WantedBy=multi-user.target
```

`sudo nano /etc/systemd/system/alr-monitor.service` (worker cek link & hapus notifikasi lewat 7 hari, tombol "Cek Semua" cuma mengantrekan):

```ini
[Unit]
Description=ALR link monitor worker
After=network.target postgresql.service

[Service]
User=bisma
WorkingDirectory=/home/bisma/alr
EnvironmentFile=/home/bisma/alr/.env
ExecStart=/home/bisma/alr/.venv/bin/flask --app run monitor-worker
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now alr alr-monitor
systemctl is-active alr alr-monitor
curl -s http://127.0.0.1:8010/health/ready   # semua harus "ok"
```

## 6. nginx

`sudo nano /etc/nginx/sites-available/alr-qas`:

```nginx
server {
    listen 80;
    server_name alr-qas.spindo.com;

    server_tokens off;

    # samakan dengan MAX_CONTENT_LENGTH aplikasi (5 lampiran x 10 MB)
    client_max_body_size 55m;

    access_log /var/log/nginx/alr-access.log;
    error_log /var/log/nginx/alr-error.log warn;

    location / {
        include /etc/nginx/proxy_params;
        proxy_pass http://unix:/run/alr/alr.sock;
        proxy_connect_timeout 5s;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    location /static/ {
        alias /home/bisma/alr/app/static/;
        access_log off;
        expires 1h;
    }

    location ~ /\.(?!well-known/) {
        return 404;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/alr-qas /etc/nginx/sites-enabled/
# nginx -t gagal = jangan reload, situs lain tetap jalan
sudo nginx -t && sudo systemctl reload nginx
```

Nginx (user `www-data`) harus bisa baca folder static: `chmod 755 /home/bisma` kalau halaman tampil tanpa CSS.
Nama `alr-qas.spindo.com` perlu didaftarkan ke DNS kantor (minta ke infra), sementara bisa dites lewat
file hosts di laptop: `192.168.0.57 alr-qas.spindo.com`.

## 7. Sekali di awal: deploy lewat pipeline

Isi `.env` server disimpan di GitLab, jadi ganti isinya di GitLab lalu deploy ulang (edit langsung di server bakal ketimpa).

1. Bikin key khusus deploy (tanpa passphrase) di server lewat MobaXterm, public key-nya dipasang di server itu juga:

   ```bash
   ssh-keygen -t ed25519 -N "" -C alr-deploy -f ~/alr_deploy
   cat ~/alr_deploy.pub >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```

2. Izin restart tanpa password, cuma buat dua service ini. Di server `sudo visudo -f /etc/sudoers.d/alr`:

   ```
   bisma ALL=(root) NOPASSWD: /usr/bin/systemctl restart alr alr-monitor
   ```

3. GitLab → Settings → CI/CD → Variables. Semua **Type: File**, **Protected** dicentang, **Expand variable reference** dimatikan,
   **Environment scope: `qas`** (`main` harus protected branch):

   | Key | Isi |
   |---|---|
   | `ENV_FILE` | isi `.env` server yang sekarang, `ENCRYPTION_KEY` wajib sama |
   | `SSH_PRIVATE_KEY` | isi `cat ~/alr_deploy`, akhiri baris kosong. Habis itu `rm ~/alr_deploy` |
   | `SSH_KNOWN_HOSTS` | hasil `ssh-keyscan 192.168.0.57`, cocokkan fingerprint-nya dengan server |

Jangan bikin variable GitLab bernama `DATABASE_URL`: nilainya ngalahin `.gitlab-ci.yml`, jadi `postgres_test` bisa
ngejalanin `db downgrade` ke database asli.

## Update versi baru

Merge ke `main` → tunggu test hijau → GitLab **Build → Pipelines** → pencet ▶ di job `deploy_qas`.

Job gagal sebelum langkah `restart` = aplikasi belum diganti; benerin lalu deploy ulang. Mau balik ke versi lama: pencet `deploy_qas` di pipeline lama
(cuma kodenya yang balik, struktur database nggak ikut turun).

Cara manual kalau pipeline mati:

```bash
cd ~/alr
.venv/bin/flask --app run backup --only database
git fetch origin && git checkout --detach origin/main
.venv/bin/pip install -r requirements.txt
.venv/bin/flask --app run db upgrade
sudo systemctl restart alr alr-monitor
```

## Kalau ada masalah

```bash
sudo journalctl -u alr -n 100          # log aplikasi
sudo journalctl -u alr-monitor -n 100  # log worker
sudo tail -50 /var/log/nginx/alr-error.log
```
