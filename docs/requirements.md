# MTOA Access Link Register (MTOA ALR) — Dokumen Requirement

## 1. Ringkasan
MTOA ALR adalah web app untuk mencatat dan menyimpan daftar link akses ICT
beserta petunjuk/kredensialnya secara terpusat, menggantikan link yang
sebelumnya tersebar. Link hanya disimpan sebagai teks (tidak dibuka otomatis).

## 2. Teknologi
| Komponen | Pilihan |
|---|---|
| Bahasa | Python 3 |
| Framework Web | Flask + Jinja2 |
| Database | PostgreSQL (`db_mtoa_alr`) |
| ORM | SQLAlchemy (parameterized query) |
| Testing | Pytest |
| Repositori & CI/CD | GitLab |

## 3. Entitas User & Role
- Username login = Email korporat.
- Profil user: Email, Nama Lengkap, Departemen, Jabatan, Role.
- Role:
  - **Admin**: mengelola master data; CRUD penuh atas seluruh data Public milik semua user.
  - **User Entry**: CRUD penuh atas data miliknya sendiri (Public & Private).

## 4. Daftar Requirement (SR)
| ID | Nama | Deskripsi |
|---|---|---|
| SR-01 | Master Category | Kategori: Web, Application, Network, General. Dikelola Admin. |
| SR-02 | Master User | Email, nama lengkap, departemen, jabatan, role, status aktif. |
| SR-03 | Data Transaksi Access | Title, category, URL, address, port, username, access note/password (terenkripsi), description, attachment, created by, visibility (Public/Private), status, created at, last changed. |
| SR-04 | RBAC Public/Private | Aturan hak akses sesuai bagian 5. |
| SR-05 | Form Input Dinamis | Field menyesuaikan kategori (Web: URL; Network: Address & Port). Kategori General: tombol "Add field" untuk menambah field satu per satu, isi field memakai editor teks dengan toolbar format. Attachment maks 5 file. |
| SR-06 | Validasi & Duplikasi | URL wajib http/https; deteksi duplikasi URL atau kombinasi Address + Port. |
| SR-07 | Validasi File Upload | Ekstensi: jpg, png, pdf, xlsx, doc, docx, txt. Validasi MIME type, maks 10MB per file, nama file diacak, created_at attachment dicatat. |
| SR-08 | Tampilan Tabel | Title, Category, URL (truncated), Description (truncated), Attachment, Created By, Created At. |
| SR-09 | Filter & Search | Pencarian keyword dan filter Category. |
| SR-10 | Export Excel | Export data yang boleh dilihat user ke .xlsx (tanpa password). |
| SR-11 | Edit & Delete | Dengan dialog konfirmasi. |
| SR-12 | Tombol Copy | Copy URL/Address ke clipboard tanpa blok teks manual. |
| SR-13 | Database Terstruktur | Skema PostgreSQL ternormalisasi sesuai naming convention. |
| SR-14 | Cek Status Link | Pengecekan status link aktif / tidak aktif. |
| SR-15 | Audit Log | Immutable: siapa, IP address, timestamp, tindakan, nilai lama vs baru. |
| SR-16 | Group / Workspace | User membuat group, mengundang anggota, dan mengisi group dengan link yang ada atau link baru. |
| SR-17 | UI Sidebar, Customizer & Dark Mode | Sidebar kiri (Dashboard, Categories, Groups, Audit Logs, Settings) + profil ringkas dengan avatar inisial maks 3 huruf (contoh: MBP); panel kustomisasi (warna aksen, compact view, font); toggle Light/Dark yang tersimpan. |

## 5. Aturan Hak Akses (RBAC)
| Aksi | Admin | User Entry (data sendiri) | User Entry (Public milik user lain) |
|---|---|---|---|
| Lihat | Semua data Public | Ya | Ya (Read-Only) |
| Copy link | Ya | Ya | Ya |
| Tambah | Ya | Ya | – |
| Ubah | Semua data Public | Ya | Tidak |
| Hapus | Semua data Public | Ya | Tidak |
| Kelola Master Data | Ya | Tidak | Tidak |

Data **Private** hanya dapat dilihat oleh pemiliknya (termasuk tidak terlihat oleh Admin).

## 6. Ringkasan Fitur Pendukung
- **Dashboard**: kumpulan link, created by, tanggal & jam dibuat, tombol Copy dan View detail.
- **Group**: owner group mengundang anggota; anggota melihat link di dalam group.
- **Audit Logs**: dicatat untuk setiap create/update/delete/login; tidak bisa diubah/dihapus.
- **Security**: lihat bagian 7.
- **Sidebar Navigation**: menu utama dan profil user aktif (Nama, Departemen, Jabatan).
- **Theme Customizer & Dark Mode**: preferensi disimpan di tabel `user_preferences` dan localStorage.

## 7. Kebutuhan Keamanan (Non-Fungsional)
1. Access note/password dienkripsi (Fernet/AES) sebelum disimpan; password login di-hash (Argon2/Bcrypt).
2. OWASP Top 10: SQLAlchemy ORM (anti SQL Injection), sanitasi input & auto-escape Jinja2 (anti XSS), CSRF token, CORS ketat.
3. Upload hardening sesuai SR-07.
4. Rate limiting pada Login dan OTP Intramail.
5. Audit log immutable sesuai SR-15.
6. Secret (DB password, encryption key) disimpan di environment variable, tidak di repositori.

## 8. Konvensi Pengembangan
- Branch: `main` (rilis), `develop` (integrasi), `feature/<nama-fitur>`.
- Commit: Conventional Commits `<type>(<scope>): <deskripsi>`.
- Naming: snake_case (modul, fungsi, tabel plural), PascalCase (class, model singular), boolean `is_/has_/can_`, koleksi bersufiks tipe data.
- Frontend: HTML, CSS, JS dipisah; backend dipisah ke routes, services, models, schemas, security, utils.

## 9. Asumsi (Perlu Konfirmasi)
- Framework Flask dipilih karena kebutuhan Jinja2 dan CSRF form.
- Isi SR-14, SR-16, SR-17 disusun ulang dari kebutuhan terbaru.
- Login menggunakan password + OTP via Intramail.
- Link Private yang dimasukkan ke group dapat dilihat anggota group tersebut.