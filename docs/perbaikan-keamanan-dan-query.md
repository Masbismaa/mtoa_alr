# Perbaikan keamanan dan query

Perubahan ini belum dijalankan lewat pytest atau migrasi di database kerja. Jalankan
pengujian dan uji migrasi PostgreSQL pada salinan database sebelum menerapkan ke server.

## Menjalankan versi baru

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app run db upgrade
.\.venv\Scripts\python.exe -m pytest -q
```

Ada dua migrasi baru: versi sesi pengguna, lalu antrean pemeriksaan dan indeks
`access_entries(category_id, created_at, id)` serta `audit_logs(user_id, created_at, id)`.
Pembuatan indeks bisa menahan penulisan pada tabel besar; siapkan jendela pemeliharaan.
Jangan membuat migrasi duplikat untuk kolom atau tabel ini.

## Perubahan perilaku keamanan

- Logout mencabut seluruh sesi akun dengan menaikkan versi sesi di database. Cookie
  lama, termasuk cookie dari sebelum migrasi ini, harus login ulang. Menonaktifkan atau
  mengaktifkan akun juga mengganti versi agar sesi lama tidak hidup kembali.
- Password dan OTP mengunci baris akun selama transaksi di PostgreSQL agar hitungan
  gagal dan pemakaian OTP tidak berlomba. SQLite tidak membuktikan perilaku konkurensi ini.
- Salah password diblokir per **email + IP** (5 kali / 15 menit, `app/security/auth_throttle.py`), bukan per
  akun, supaya orang lain tidak bisa sengaja mengunci akun orang. Email yang tidak terdaftar diblokir dengan
  pesan yang sama. Saat sebuah IP terblokir, pemilik akun mendapat notifikasi lonceng berisi IP tersebut.
  Akun baru dikunci (`users.locked_until`, bisa dibuka admin) hanya jika salah OTP 5 kali, dan pesan
  "Akun dikunci" hanya muncul kalau password-nya benar. Hitungan blokir disimpan di `RATELIMIT_STORAGE_URI`
  (Redis di production) dan tetap berjalan walau `RATELIMIT_ENABLED=False`.
- Pendaftaran wajib verifikasi email. Akun di `users` baru dibuat setelah kode yang dikirim ke email itu
  dimasukkan. Sebelum itu, setiap percobaan daftar disimpan sendiri-sendiri di `pending_registrations`
  (migrasi `b4d9e2a7c1f3`) dengan token yang hanya ada di session pendaftarnya. Akibatnya, kode hanya berlaku
  untuk percobaan itu sendiri, dan orang lain yang mendaftar memakai email yang sama tidak bisa mengubah
  password atau profil percobaan pemiliknya. Layar pendaftaran selalu sama, baik untuk email baru maupun
  email yang sudah terdaftar. Pemilik email terdaftar hanya menerima email pemberitahuan (maks. sekali per
  10 menit). Kode daftar ke satu email dibatasi 5 kali per 15 menit, dan percobaan yang tidak diverifikasi
  dihapus setelah 24 jam. Perintah `create-admin` tetap langsung membuat akun aktif.
- SMTP sudah mendukung STARTTLS/TLS dengan verifikasi sertifikat. Isi `SMTP_HOST`,
  `SMTP_FROM`, port, serta kredensial relay sesuai arahan pengelola intramail. Mode console
  tetap hanya untuk development. Pengiriman gagal membatalkan OTP dan memberi pesan aman.
- Production menolak limiter `memory://`; gunakan Redis yang sama untuk semua proses.
  `TRUSTED_PROXY_COUNT` harus cocok dengan rantai proxy sebenarnya, dan akses langsung
  ke backend harus dibatasi. Nilai sembarang dapat membuat header IP pengunjung dipercaya.
- Respons dinamis memakai `private, no-store`, nosniff, proteksi frame, dan CSP terbatas
  untuk frame/base/object. HSTS aktif pada production yang harus dilayani lewat HTTPS.
  CSP ini belum membatasi sumber JavaScript; jangan menganggap seluruh risiko XSS selesai.
- Upload baru `.doc` tidak diterima karena signature OLE tidak membuktikan dokumen Word.
  Unduhan lampiran lama tetap tersedia. OOXML diperiksa struktur, batas dekompresi, bagian
  makro/objek tertanam. Pemeriksaan struktur bukan pengganti antivirus.
- ClamAV INSTREAM memindai upload sebelum disimpan. Production wajib mengisi
  `UPLOAD_SCANNER_HOST`; jika scanner mati atau menolak file, upload ditolak. Batasi akses
  clamd ke aplikasi saja; protokol ini bukan TLS. Sesuaikan batas INSTREAM clamd dengan
  batas lampiran 10 MiB. Development boleh tanpa scanner.
- Kuota awal 500 MiB per akun, diatur `UPLOAD_USER_QUOTA_BYTES`. Upload paralel diserialkan
  lewat baris akun. Penggantian lampiran menghitung file lama sampai transaksi selesai;
  akun penuh perlu menghapus lampiran dahulu sebelum mengunggah penggantinya.

## Pemeriksaan link tetap manual

Tombol admin hanya memasukkan permintaan ke database lalu segera memberi respons.
Satu worker yang memegang token memeriksa data; klik bersamaan tidak membuat dua job.
Worker mengambil 20 target per batch, menutup transaksi saat menghubungi jaringan,
dan menyimpan progres serta hasil tiap batch. Kegagalan bisa meninggalkan hasil parsial
yang ditandai gagal pada panel. Worker hanya mengerjakan permintaan tombol, tanpa jadwal
atau pemicu setelah penambahan data.

Jalankan pada terminal terpisah saat development, atau sebagai service pada production:

```powershell
.\.venv\Scripts\python.exe -m flask --app run monitor-worker
```

`monitor-worker --once` memproses satu antrean lalu berhenti. `check-links` menjalankan
satu pemeriksaan manual di terminal dengan kunci yang sama. Jika worker mati, antrean
tetap tersimpan. `recover-link-monitor` mencabut job yang tidak memberi progres selama
lima menit; worker lama ditolak sebelum menulis batch berikutnya. Setelah mencabut job,
restart worker yang macet lalu minta pemeriksaan lagi.

Target harus IP publik secara default; loopback, link-local/metadata, multicast, CGNAT
dan IPv6 transition ditolak, termasuk hasil DNS/redirect. Untuk jaringan kantor, operator
dapat mengisi `LINK_CHECK_ALLOW_PRIVATE_NETWORKS=true` **setelah** memasang pembatasan
egress agar server tidak dapat menjangkau alamat manajemen, database, metadata atau
layanan lain yang tidak diperlukan. Izin intranet luas tetap menambah risiko SSRF;
aplikasi tidak dapat menyimpulkan semua alamat privat mana yang boleh dihubungi.
Sertifikat selalu diverifikasi; CA internal bisa lewat `LINK_CHECK_CA_FILE`.
Timeout koneksi bukan batas waktu DNS resolver OS; worker dan resolver tetap perlu
pengawasan dan batas sumber daya pada server.

## Efisiensi dan pemeliharaan

Forum mengambil link terbaru per kategori dengan window SQL satu kali, termasuk
penentuan terbaru di seluruh keturunannya. Pemilihan kategori membangun pohon satu kali.
Jumlah link group dihitung SQL dengan aturan anggota/visibilitas, bukan membuka semua
link dan viewer per group. Grafik menghitung tanggal WIB di database, ringkasan monitor
memakai GROUP BY. Pembacaan preferensi tidak menulis DB; pembaruan layout diserialkan
agar pembaruan dua tabel tidak saling menimpa. Gaya font/alignment Excel dipakai ulang.
Pencarian substring masih perlu EXPLAIN pada data nyata; indeks btree baru tidak
mempercepat semua bentuk LIKE. Pilih indeks trigram PostgreSQL setelah mengukur rencana
query, ukuran indeks, dan biaya tulis. Tidak ada klaim latensi produksi dari inspeksi kode.

File yang gagal dihapus setelah commit tidak lagi menutupi hasil transaksi dengan error.
Untuk menemukan file yatim, termasuk sisa rollback/crash:

```powershell
.\.venv\Scripts\python.exe -m flask --app run cleanup-attachments
# Setelah jumlah dan backup diperiksa:
.\.venv\Scripts\python.exe -m flask --app run cleanup-attachments --delete
```

Perintah default hanya menghitung; penghapusan hanya untuk file tanpa referensi database
yang sudah berumur 24 jam. Jalankan pemeliharaan pada folder upload khusus aplikasi dan
buat backup database serta lampiran bersama. Ini belum merupakan backup atau pemindaian
ulang antivirus untuk semua lampiran lama.
