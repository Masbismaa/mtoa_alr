"""Konstanta global aplikasi; satu sumber kebenaran untuk role, tema, dan kategori default."""
# Role pengguna
ROLE_ADMIN = "admin"
ROLE_USER_ENTRY = "user_entry"
ROLE_LIST = [ROLE_ADMIN, ROLE_USER_ENTRY]

# Preferensi tampilan
THEME_MODE_LIGHT = "light"
THEME_MODE_DARK = "dark"
THEME_MODE_LIST = [THEME_MODE_LIGHT, THEME_MODE_DARK]
DEFAULT_ACCENT_COLOR = "#0a6ed1"
DEFAULT_FONT_FAMILY = "system"

# Kategori default yang di-seed ke tabel categories
DEFAULT_CATEGORY_LIST = [
    {"name": "Web", "description": "Web-based application links (URL)"},
    {"name": "Application", "description": "Desktop or internal applications"},
    {"name": "Network", "description": "Network devices (Address & Port)"},
    {"name": "General", "description": "Other access that doesn't fit the categories above"},
]

# nama kategori bawaan: ga bisa di ganti nama, dinonaktifkan, atau dihapus (Aturan formnya nempel ke nama)
DEFAULT_CATEGORY_NAME_SET = {category["name"] for category in DEFAULT_CATEGORY_LIST}
MIN_CATEGORY_NAME_LENGTH = 2
MAX_CATEGORY_NAME_LENGTH = 50
MAX_CATEGORY_DESCRIPTION_LENGTH = 255

# kategori bertingkat: utama + 3 tingkat sub
MAX_CATEGORY_DEPTH = 4
CATEGORY_PATH_SEPARATOR = " › "
# ikon & warna kategori utama di tampilan forum, kategori lain pake gaya default
CATEGORY_STYLE_DICT = {
    "Web": {"icon": "globe", "color_class": "bg-blue"},
    "Application": {"icon": "apps", "color_class": "bg-green"},
    "Network": {"icon": "network", "color_class": "bg-orange"},
    "General": {"icon": "file", "color_class": "bg-purple"},
}
DEFAULT_CATEGORY_STYLE = {"icon": "category", "color_class": "bg-secondary"}

# Audit log
# jenis aksi yg boleh dicatat, di luar ini ditolak
AUDIT_ACTION_CREATE = "create"
AUDIT_ACTION_UPDATE = "update"
AUDIT_ACTION_DELETE = "delete"
AUDIT_ACTION_LOGIN = "login"
AUDIT_ACTION_LOGIN_FAILED = "login_failed"
AUDIT_ACTION_LOGOUT = "logout"
AUDIT_ACTION_EXPORT = "export"
# ganti password (lewat Settings / lupa password), import Excel
AUDIT_ACTION_PASSWORD_CHANGE = "password_change"
AUDIT_ACTION_IMPORT = "import"
AUDIT_ACTION_LIST = [
    AUDIT_ACTION_CREATE,
    AUDIT_ACTION_UPDATE,
    AUDIT_ACTION_DELETE,
    AUDIT_ACTION_LOGIN,
    AUDIT_ACTION_LOGIN_FAILED,
    AUDIT_ACTION_LOGOUT,
    AUDIT_ACTION_EXPORT,
    AUDIT_ACTION_PASSWORD_CHANGE,
    AUDIT_ACTION_IMPORT,
]

# riwayat per data (kartu History di detail link): sekian catatan terbaru aja
ENTITY_HISTORY_LIMIT = 50

# field yg isinya rahasia, di audit log diganti bintang-bintang
SENSITIVE_FIELD_SET = {"password", "password_hash", "access_note", "encrypted_access_note", "otp_code"}
MASKED_VALUE = "********"

# Keamanan input
MAX_TEXT_LENGTH = 1000
MIN_PASSWORD_LENGTH = 8

# Login & OTP
# salah password / OTP (digabung) 3 kali -> akunnya dikunci (users.locked_until, status Locked, bisa di-unlock admin)
# + email itu diblokir di auth_throttle biar email ga terdaftar dapet pesan yg sama
LOGIN_MAX_FAILED_COUNT = 3
LOGIN_LOCK_MINUTES = 15
# email "kamu sudah punya akun" (ada yg daftar pakai email terdaftar) maksimal sekali per sekian menit per email
REGISTER_NOTICE_COOLDOWN_MINUTES = 10
# kode verifikasi daftar ke satu email maksimal sekian kali per sekian menit (anti spam kotak masuk orang)
REGISTER_CODE_MAX_COUNT = 5
REGISTER_CODE_WINDOW_MINUTES = 15
# lupa password: percobaan masukin kode per email + IP per hari. Per IP biar tebakan orang lain ga ngabisin jatah pemiliknya
RESET_ATTEMPT_MAX_COUNT = 10
# lupa password: kode reset per email per hari. Tiap kode cuma 5x coba, jadi total tebakan lintas IP maks. 10 x 5 sehari
RESET_CODE_DAILY_MAX_COUNT = 10
# percobaan daftar yg ga diverifikasi dibuang setelah sekian jam
PENDING_REGISTRATION_EXPIRE_HOURS = 24

# aturan OTP
OTP_LENGTH = 6
OTP_EXPIRE_MINUTES = 5
OTP_MAX_ATTEMPT_COUNT = 5
OTP_RESEND_COOLDOWN_SECONDS = 60

# cara kirim OTP
OTP_DELIVERY_CONSOLE = "console"
OTP_DELIVERY_SMTP = "smtp"

# OTP dipake buat login, verifikasi email pendaftaran, & lupa password (beda judul email).
# login & reset disimpen di otp_codes (kolom purpose), kode daftar di pending_registrations
OTP_PURPOSE_LOGIN = "login"
OTP_PURPOSE_REGISTER = "register"
OTP_PURPOSE_RESET = "reset"

# batas panjang password (argon2 lemot kalau inputnya kepanjangan)
MAX_PASSWORD_LENGTH = 128

# nama key di session buat nyimpen user yg lagi nunggu isi OTP
SESSION_PENDING_USER_KEY = "pending_user_id"
# data pendaftaran yg lagi nunggu kode verifikasi email: {"email", "sent_at", "attempt_count"}
SESSION_PENDING_REGISTER_KEY = "pending_register"
# lupa password yg lagi nunggu kode: {"email", "sent_at", "attempt_count"} (pola sama kayak daftar)
SESSION_PASSWORD_RESET_KEY = "password_reset"

# UI & Customizer
# pilihan warna aksen: hex disimpen di DB, key dipake CSS (data-accent)
ACCENT_COLOR_OPTION_LIST = [
    {"key": "blue", "hex": "#0a6ed1", "label": "Blue"},
    {"key": "yellow", "hex": "#ffd23f", "label": "Yellow"},
    {"key": "pink", "hex": "#ff6b9d", "label": "Pink"},
    {"key": "lime", "hex": "#a3e635", "label": "Lime"},
    {"key": "teal", "hex": "#2ec4b6", "label": "Teal"},
    {"key": "purple", "hex": "#b388ff", "label": "Purple"},
]
ACCENT_KEY_BY_HEX_DICT = {option["hex"]: option["key"] for option in ACCENT_COLOR_OPTION_LIST}
DEFAULT_ACCENT_KEY = "blue"

# pilihan font
FONT_FAMILY_OPTION_LIST = [
    {"key": "system", "label": "System"},
    {"key": "mono", "label": "Mono"},
    {"key": "serif", "label": "Serif"},
]
FONT_FAMILY_KEY_LIST = [option["key"] for option in FONT_FAMILY_OPTION_LIST]

# label role yg tampil di UI
ROLE_LABEL_DICT = {ROLE_ADMIN: "Admin", ROLE_USER_ENTRY: "User Entry"}

# Access Entry
VISIBILITY_PUBLIC = "public"
VISIBILITY_PRIVATE = "private"
VISIBILITY_LIST = [VISIBILITY_PUBLIC, VISIBILITY_PRIVATE]
VISIBILITY_LABEL_DICT = {VISIBILITY_PUBLIC: "Public", VISIBILITY_PRIVATE: "Private"}

# status link (diisi pengecekan otomatis lewat command check-links)
LINK_STATUS_UNKNOWN = "unknown"
LINK_STATUS_UP = "up"
LINK_STATUS_DOWN = "down"
LINK_STATUS_LIST = [LINK_STATUS_UNKNOWN, LINK_STATUS_UP, LINK_STATUS_DOWN]
LINK_STATUS_LABEL_DICT = {
    LINK_STATUS_UNKNOWN: "Not checked",
    LINK_STATUS_UP: "Up",
    LINK_STATUS_DOWN: "Down",
}

# cek status link
LINK_CHECK_TIMEOUT_SECONDS = 5
LINK_CHECK_MAX_WORKER_COUNT = 10
LINK_CHECK_MAX_REDIRECT_COUNT = 3
# batas waktu TOTAL 1 link (DNS + koneksi + redirect); lewat dari ini dianggap tidak aktif
LINK_CHECK_TARGET_DEADLINE_SECONDS = 30
# semua slot pemeriksa keisi thread macet selama ini -> pemeriksaan dihentiin biar worker ga ketahan
LINK_CHECK_STUCK_LIMIT_SECONDS = 120
# antrean ga diambil worker sekian detik -> halaman Link Monitoring kasih peringatan worker kemungkinan mati
MONITOR_WORKER_WAIT_WARNING_SECONDS = 60
# pemeriksaan jalan tapi ga ada kemajuan sekian detik -> peringatan (satu link paling lama 30 dtk)
MONITOR_STALL_WARNING_SECONDS = 120
LINK_CHECK_USER_AGENT = "ALR-LinkCheck/1.0"
LINK_STATUS_NOTE_MAX_LENGTH = 255

# nama kategori default (harus sama dengan DEFAULT_CATEGORY_LIST)
CATEGORY_NAME_WEB = "Web"
CATEGORY_NAME_APPLICATION = "Application"
CATEGORY_NAME_NETWORK = "Network"
CATEGORY_NAME_GENERAL = "General"

# field khusus per kategori.
# judul, deskripsi, visibilitas selalu ada. username + access note ada kalau has_credential_field True
CATEGORY_SPECIFIC_FIELD_LIST = ["url", "address", "port"]
CREDENTIAL_FIELD_LIST = ["username", "access_note"]
CATEGORY_FIELD_RULE_DICT = {
    CATEGORY_NAME_WEB: {"field_list": ["url"], "required_field_list": ["url"], "has_custom_field": False, "has_credential_field": True},
    CATEGORY_NAME_APPLICATION: {"field_list": ["url", "address"], "required_field_list": [], "has_custom_field": False, "has_credential_field": True},
    CATEGORY_NAME_NETWORK: {"field_list": ["address", "port"], "required_field_list": ["address"], "has_custom_field": False, "has_credential_field": True},
    CATEGORY_NAME_GENERAL: {"field_list": [], "required_field_list": [], "has_custom_field": True, "has_credential_field": False},
}
# kategori baru bikinan admin (nanti) pake aturan ini
DEFAULT_CATEGORY_FIELD_RULE = {"field_list": ["url", "address", "port"], "required_field_list": [], "has_custom_field": False, "has_credential_field": True}

# field tambahan kategori General (tambah 1 per klik)
CUSTOM_FIELD_MAX_COUNT = 10

# batas panjang input
MAX_TITLE_LENGTH = 150
MAX_URL_LENGTH = 2048
MAX_ADDRESS_LENGTH = 255
MAX_USERNAME_LENGTH = 150
MAX_ACCESS_NOTE_LENGTH = 2000
MAX_FIELD_LABEL_LENGTH = 100
MAX_RICH_TEXT_LENGTH = 20000

# skema URL yg boleh (dipake validasi URL & link di editor)
ALLOWED_URL_SCHEME_SET = {"http", "https"}

# tag HTML yg boleh dari editor teks, sisanya dibuang
RICH_TEXT_ALLOWED_TAG_SET = {
    "p", "div", "br", "b", "strong", "i", "em", "u", "s", "strike", "ul", "ol", "li", "code", "pre", "a",
    "h1", "h2", "h3", "blockquote", "hr", "font",
}
# pilihan toolbar editor ala Word. Dipake toolbar (template) & sanitizer (nilai di luar daftar dibuang)
RICH_TEXT_BLOCK_LIST = [("p", "Normal"), ("h1", "Heading 1"), ("h2", "Heading 2"), ("h3", "Heading 3"),
                        ("blockquote", "Quote"), ("pre", "Code Block")]
RICH_TEXT_FONT_LIST = ["Calibri", "Arial", "Times New Roman", "Georgia", "Consolas"]
# (nilai fontSize browser 1-7, label pt ala Word)
RICH_TEXT_SIZE_LIST = [("1", "8"), ("2", "10"), ("3", "12"), ("4", "14"), ("5", "18"), ("6", "24"), ("7", "36")]
# warna yg tetep kebaca di tema terang & gelap
RICH_TEXT_COLOR_LIST = [("#d63939", "Red"), ("#f76707", "Orange"), ("#f59f00", "Yellow"), ("#2fb344", "Green"),
                        ("#206bc4", "Blue"), ("#ae3ec9", "Purple"), ("#667382", "Gray")]

ATTACHMENT_MAX_COUNT = 5
ATTACHMENT_MAX_SIZE_BYTES = 10 * 1024 * 1024
MAX_FILENAME_LENGTH = 255

# ekstensi yg boleh + content type yg dipake pas download
ATTACHMENT_CONTENT_TYPE_BY_EXTENSION_DICT = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
}
ATTACHMENT_EXTENSION_LIST = list(ATTACHMENT_CONTENT_TYPE_BY_EXTENSION_DICT)

# jumlah baris per halaman di semua tabel (dashboard, kategori, audit log, users)
PER_PAGE = 10

# notifikasi lonceng
MAX_NOTIFICATION_MESSAGE_LENGTH = 255
NOTIFICATION_MENU_LIMIT = 8
# notifikasi yg udah dibaca & lebih tua dari ini dibuang perintah cleanup-old-data
NOTIFICATION_RETENTION_DAYS = 90
MAX_SEARCH_KEYWORD_LENGTH = 100

# Select Screen ala SAP: * = wildcard, tiap isian maksimal sekian nilai (Multi Selection)
SEARCH_WILDCARD = "*"
SELECTION_MAX_VALUE_COUNT = 20
SELECTION_EXCLUDE_SUFFIX = "__not"

# tabel ala ALV: parameter urutan di URL (?sort=judul / ?sort=-judul) & batas lebar kolom yg boleh disimpen
TABLE_SORT_KEY = "sort"
TABLE_SORT_DESC_PREFIX = "-"
TABLE_COLUMN_MIN_WIDTH = 60
TABLE_COLUMN_MAX_WIDTH = 800

# group
GROUP_ROLE_OWNER = "owner"
GROUP_ROLE_MEMBER = "member"
GROUP_ROLE_LIST = [GROUP_ROLE_OWNER, GROUP_ROLE_MEMBER]
GROUP_MEMBER_STATUS_INVITED = "invited"
GROUP_MEMBER_STATUS_ACTIVE = "active"
GROUP_MEMBER_STATUS_LIST = [GROUP_MEMBER_STATUS_INVITED, GROUP_MEMBER_STATUS_ACTIVE]
MAX_GROUP_NAME_LENGTH = 100
MAX_GROUP_DESCRIPTION_LENGTH = 500

# halaman audit log
AUDIT_ACTION_LABEL_DICT = {
    AUDIT_ACTION_CREATE: "Create",
    AUDIT_ACTION_UPDATE: "Change",
    AUDIT_ACTION_DELETE: "Delete",
    AUDIT_ACTION_LOGIN: "Login",
    AUDIT_ACTION_LOGIN_FAILED: "Login Failed",
    AUDIT_ACTION_LOGOUT: "Logout",
    AUDIT_ACTION_EXPORT: "Export",
    AUDIT_ACTION_PASSWORD_CHANGE: "Password Change",
    AUDIT_ACTION_IMPORT: "Import",
}
# nama tabel yg dicatat di audit log -> label di UI
AUDIT_ENTITY_LABEL_DICT = {
    "users": "User",
    "user_preferences": "Display Preferences",
    "access_entries": "Link",
    "groups": "Group",
    "group_members": "Group Member",
    "group_entries": "Group Link",
    "categories": "Category",
    "link_monitor_settings": "Link Monitoring",
    "backups": "Backup",
}

# dashboard (grafik & aktivitas)
# feed aktivitas tim: sekian hari terakhir, maks sekian baris (abis digabung), link Down milik sendiri maks sekian
DASHBOARD_ACTIVITY_DAY_COUNT = 7
DASHBOARD_TEAM_ACTIVITY_LIMIT = 8
DASHBOARD_ATTENTION_LIMIT = 5
# folder Favorites di Easy Access: sisanya dibuka lewat Link List filter Favorites
EASY_ACCESS_FAVORITE_LIMIT = 20
DASHBOARD_RECENT_ACTIVITY_LIMIT = 5

# kelola user
USER_STATUS_ACTIVE = "active"
USER_STATUS_LOCKED = "locked"
USER_STATUS_INACTIVE = "inactive"
USER_STATUS_LABEL_DICT = {
    USER_STATUS_ACTIVE: "Active",
    USER_STATUS_LOCKED: "Locked",
    USER_STATUS_INACTIVE: "Inactive",
}

# hapus akun: data diri diganti biar email aslinya bisa dipake daftar lagi
DELETED_USER_NAME = "Deleted account"
DELETED_USER_PROFILE_TEXT = "-"
# .invalid itu domain cadangan, dijamin ga bakal jadi email beneran
DELETED_USER_EMAIL_DOMAIN = "deleted.invalid"
# bukan format argon2, jadi verify_password selalu False
UNUSABLE_PASSWORD_HASH = "!"

# export kat excel
EXPORT_MAX_ROW_COUNT = 5000
# variant Kriteria Pencarian (Save as Variant): maks per layar per user
SELECTION_VARIANT_MAX_COUNT = 20
MAX_VARIANT_NAME_LENGTH = 50
MAX_VARIANT_QUERY_LENGTH = 2000

# hapus banyak link (admin): maks id per permintaan, sama kayak isi 1 halaman tabel paling banyak
BULK_DELETE_MAX_COUNT = 100

# import dari excel: maks baris per file (semua dicek dulu baru disimpen dalam 1 transaksi)
IMPORT_MAX_ROW_COUNT = 500
EXPORT_FORMULA_PREFIX_TUPLE = ("=", "+", "-", "@", "\t","\r")
XLSX_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
