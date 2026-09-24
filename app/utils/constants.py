"""Konstanta global aplikasi; satu sumber kebenaran untuk role, tema, dan kategori default (DRY)."""

# --- Role pengguna (SR-02, SR-04) ---
ROLE_ADMIN = "admin"
ROLE_USER_ENTRY = "user_entry"
ROLE_LIST = [ROLE_ADMIN, ROLE_USER_ENTRY]

# --- Preferensi tampilan (SR-17) ---
THEME_MODE_LIGHT = "light"
THEME_MODE_DARK = "dark"
THEME_MODE_LIST = [THEME_MODE_LIGHT, THEME_MODE_DARK]
DEFAULT_ACCENT_COLOR = "#0a6ed1"
DEFAULT_FONT_FAMILY = "system"

# --- Kategori default yang di-seed ke tabel categories (SR-01) ---
DEFAULT_CATEGORY_LIST = [
    {"name": "Web", "description": "Link aplikasi berbasis web (URL)"},
    {"name": "Application", "description": "Aplikasi desktop atau aplikasi internal"},
    {"name": "Network", "description": "Perangkat jaringan (Address & Port)"},
    {"name": "General", "description": "Akses lain yang tidak masuk kategori di atas"},
]