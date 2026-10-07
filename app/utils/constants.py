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
    {"name": "Web", "description": "Link aplikasi berbasis web (URL)"},
    {"name": "Application", "description": "Aplikasi desktop atau aplikasi internal"},
    {"name": "Network", "description": "Perangkat jaringan (Address & Port)"},
    {"name": "General", "description": "Akses lain yang tidak masuk kategori di atas"},
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
AUDIT_ACTION_LIST = [
    AUDIT_ACTION_CREATE,
    AUDIT_ACTION_UPDATE,
    AUDIT_ACTION_DELETE,
    AUDIT_ACTION_LOGIN,
    AUDIT_ACTION_LOGIN_FAILED,
    AUDIT_ACTION_LOGOUT,
    AUDIT_ACTION_EXPORT,
]

# field yg isinya rahasia, di audit log diganti bintang-bintang
SENSITIVE_FIELD_SET = {"password", "password_hash", "access_note", "encrypted_access_note", "otp_code"}
MASKED_VALUE = "********"

# Keamanan input
MAX_TEXT_LENGTH = 1000
MIN_PASSWORD_LENGTH = 8

# Login & OTP
# salah password 5 kali -> akun dikunci sementara
LOGIN_MAX_FAILED_COUNT = 5
LOGIN_LOCK_MINUTES = 15

# aturan OTP
OTP_LENGTH = 6
OTP_EXPIRE_MINUTES = 5
OTP_MAX_ATTEMPT_COUNT = 5
OTP_RESEND_COOLDOWN_SECONDS = 60

# cara kirim OTP
OTP_DELIVERY_CONSOLE = "console"
OTP_DELIVERY_SMTP = "smtp"

# batas panjang password (argon2 lemot kalau inputnya kepanjangan)
MAX_PASSWORD_LENGTH = 128

# nama key di session buat nyimpen user yg lagi nunggu isi OTP
SESSION_PENDING_USER_KEY = "pending_user_id"

# UI & Customizer
# pilihan warna aksen: hex disimpen di DB, key dipake CSS (data-accent)
ACCENT_COLOR_OPTION_LIST = [
    {"key": "blue", "hex": "#0a6ed1", "label": "Biru"},
    {"key": "yellow", "hex": "#ffd23f", "label": "Kuning"},
    {"key": "pink", "hex": "#ff6b9d", "label": "Pink"},
    {"key": "lime", "hex": "#a3e635", "label": "Lime"},
    {"key": "teal", "hex": "#2ec4b6", "label": "Tosca"},
    {"key": "purple", "hex": "#b388ff", "label": "Ungu"},
]
ACCENT_KEY_BY_HEX_DICT = {option["hex"]: option["key"] for option in ACCENT_COLOR_OPTION_LIST}
DEFAULT_ACCENT_KEY = "blue"

# pilihan font
FONT_FAMILY_OPTION_LIST = [
    {"key": "system", "label": "Sistem"},
    {"key": "mono", "label": "Mono"},
    {"key": "serif", "label": "Serif"},
]
FONT_FAMILY_KEY_LIST = [option["key"] for option in FONT_FAMILY_OPTION_LIST]

# label role yg tampil di UI
ROLE_LABEL_DICT = {ROLE_ADMIN: "Admin", ROLE_USER_ENTRY: "User Entry"}

# hak akses yg bisa di-grant admin ke user biasa (admin otomatis punya semua)
PERMISSION_MANAGE_CATEGORIES = "manage_categories"
PERMISSION_VIEW_AUDIT_LOGS = "view_audit_logs"
PERMISSION_EDIT_PUBLIC_ENTRIES = "edit_public_entries"
PERMISSION_LIST = [PERMISSION_MANAGE_CATEGORIES, PERMISSION_VIEW_AUDIT_LOGS, PERMISSION_EDIT_PUBLIC_ENTRIES]
PERMISSION_INFO_DICT = {
    PERMISSION_MANAGE_CATEGORIES: {
        "label": "Kelola kategori", "short_label": "Kategori",
        "description": "Tambah, edit, nonaktifkan, dan hapus kategori di menu Categories.",
    },
    PERMISSION_VIEW_AUDIT_LOGS: {
        "label": "Lihat audit log", "short_label": "Audit Log",
        "description": "Buka menu Audit Logs. Isi data Private milik orang lain tetap tersembunyi.",
    },
    PERMISSION_EDIT_PUBLIC_ENTRIES: {
        "label": "Edit link Public orang lain", "short_label": "Edit Public",
        "description": "Ubah dan hapus link Public milik user lain. Link Private tetap tidak bisa.",
    },
}

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
    LINK_STATUS_UNKNOWN: "Belum dicek",
    LINK_STATUS_UP: "Aktif",
    LINK_STATUS_DOWN: "Tidak aktif",
}

# cek status link
LINK_CHECK_TIMEOUT_SECONDS = 5
LINK_CHECK_MAX_WORKER_COUNT = 10
LINK_CHECK_MAX_REDIRECT_COUNT = 3
LINK_CHECK_USER_AGENT = "ALR-LinkCheck/1.0"
LINK_STATUS_NOTE_MAX_LENGTH = 255

# Link Monitoring: dicek otomatis lewat command check-links (Task Scheduler/cron) + tombol admin

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
RICH_TEXT_ALLOWED_TAG_SET = {"p", "div", "br", "b", "strong", "i", "em", "u", "ul", "ol", "li", "code", "pre", "a"}

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
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
}
ATTACHMENT_EXTENSION_LIST = list(ATTACHMENT_CONTENT_TYPE_BY_EXTENSION_DICT)

# jumlah baris per halaman di semua tabel (dashboard, kategori, audit log, users)
PER_PAGE = 10
MAX_SEARCH_KEYWORD_LENGTH = 100

# Select Screen ala SAP: * = wildcard, tiap isian maksimal sekian nilai (Multi Selection)
SEARCH_WILDCARD = "*"
SELECTION_MAX_VALUE_COUNT = 20
SELECTION_EXCLUDE_SUFFIX = "__not"

# group
GROUP_ROLE_OWNER = "owner"
GROUP_ROLE_MEMBER = "member"
GROUP_ROLE_LIST = [GROUP_ROLE_OWNER, GROUP_ROLE_MEMBER]
GROUP_MEMBER_STATUS_INVITED = "invited"
GROUP_MEMBER_STATUS_ACTIVE = "active"
GROUP_MEMBER_STATUS_LIST = [GROUP_MEMBER_STATUS_INVITED, GROUP_MEMBER_STATUS_ACTIVE]
MAX_GROUP_NAME_LENGTH = 100
MAX_GROUP_DESCRIPTION_LENGTH = 500
GROUP_ENTRY_OPTION_LIMIT = 200

# halaman audit log
AUDIT_ACTION_LABEL_DICT = {
    AUDIT_ACTION_CREATE: "Tambah",
    AUDIT_ACTION_UPDATE: "Ubah",
    AUDIT_ACTION_DELETE: "Hapus",
    AUDIT_ACTION_LOGIN: "Login",
    AUDIT_ACTION_LOGIN_FAILED: "Login Gagal",
    AUDIT_ACTION_LOGOUT: "Logout",
    AUDIT_ACTION_EXPORT: "Export",
}
# nama tabel yg dicatat di audit log -> label di UI
AUDIT_ENTITY_LABEL_DICT = {
    "users": "User",
    "user_preferences": "Preferensi Tampilan",
    "access_entries": "Data Link",
    "groups": "Group",
    "group_members": "Anggota Group",
    "group_entries": "Link di Group",
    "categories": "Kategori",
    "link_monitor_settings": "Link Monitoring",
}

# dashboard (grafik & aktivitas)
DASHBOARD_CHART_DAY_COUNT = 7
DASHBOARD_RECENT_ACTIVITY_LIMIT = 5

# kelola user
USER_STATUS_ACTIVE = "active"
USER_STATUS_LOCKED = "locked"
USER_STATUS_INACTIVE = "inactive"
USER_STATUS_LABEL_DICT = {
    USER_STATUS_ACTIVE: "Aktif",
    USER_STATUS_LOCKED: "Terkunci",
    USER_STATUS_INACTIVE: "Nonaktif",
}

# hapus akun: data diri diganti biar email aslinya bisa dipake daftar lagi
DELETED_USER_NAME = "Akun dihapus"
DELETED_USER_PROFILE_TEXT = "-"
# .invalid itu domain cadangan, dijamin ga bakal jadi email beneran
DELETED_USER_EMAIL_DOMAIN = "deleted.invalid"
# bukan format argon2, jadi verify_password selalu False
UNUSABLE_PASSWORD_HASH = "!"

# export kat excel
EXPORT_MAX_ROW_COUNT = 5000
EXPORT_FORMULA_PREFIX_TUPLE = ("=", "+", "-", "@", "\t","\r")
XLSX_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
