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

# Audit log
# jenis aksi yg boleh dicatat, di luar ini ditolak
AUDIT_ACTION_CREATE = "create"
AUDIT_ACTION_UPDATE = "update"
AUDIT_ACTION_DELETE = "delete"
AUDIT_ACTION_LOGIN = "login"
AUDIT_ACTION_LOGIN_FAILED = "login_failed"
AUDIT_ACTION_LOGOUT = "logout"
AUDIT_ACTION_LIST = [
    AUDIT_ACTION_CREATE,
    AUDIT_ACTION_UPDATE,
    AUDIT_ACTION_DELETE,
    AUDIT_ACTION_LOGIN,
    AUDIT_ACTION_LOGIN_FAILED,
    AUDIT_ACTION_LOGOUT,
]

# field yg isinya rahasia, di audit log diganti bintang-bintang
SENSITIVE_FIELD_SET = {"password", "password_hash", "access_note", "encrypted_access_note", "otp_code"}
MASKED_VALUE = "********"

# Keamanan iput
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