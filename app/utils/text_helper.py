"""Helper olah teks yg dipake di banyak tempat."""
from app.utils.constants import (
    AUDIT_ACTION_LABEL_DICT,
    AUDIT_ENTITY_LABEL_DICT,
    LINK_STATUS_LABEL_DICT,
    ROLE_LABEL_DICT,
    USER_STATUS_LABEL_DICT,
    VISIBILITY_LABEL_DICT,
)

def normalize_email(value):
    """Rapihin email: hapus spasi di ujung + huruf kecil semua."""
    return (value or "").strip().lower()

def mask_email(email):
    """Samarin email buat ditampilin, misal user.login@spindo.com -> us********@spindo.com."""
    local_part, _, domain = email.partition("@")
    visible_text = local_part[:2]
    # minimal 1 bintang biar tetep keliatan disamarin
    hidden_count = max(len(local_part) - len(visible_text), 1)
    return f"{visible_text}{'*' * hidden_count}@{domain}"

def get_initials(full_name, max_letter_count=3):
    """Ambil huruf depan nama buat avatar (maks 3), misal 'Mochammad Bisma Prasetya' -> 'MBP'."""
    word_list = [word for word in (full_name or "").split() if word]
    if not word_list:
        return "?"
    return "".join(word[0] for word in word_list[:max_letter_count]).upper()

def get_role_label(role):
    """Ubah kode role jadi label yg enak dibaca, misal 'user_entry' -> 'User Entry'."""
    return ROLE_LABEL_DICT.get(role, role)

def get_visibility_label(visibility):
    """Ubah kode visibilitas jadi label, misal 'public' -> 'Public'."""
    return VISIBILITY_LABEL_DICT.get(visibility, visibility)

def get_link_status_label(status):
    """Ubah kode status link jadi label, misal 'unknown' -> 'Belum dicek'."""
    return LINK_STATUS_LABEL_DICT.get(status, status)

def format_file_size(size_bytes):
    if size_bytes is None:
        return "-"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f} KB"
    return f"{size_bytes/(1024*1024):.1f} MB"

def get_audit_action_label(action):
    """Ubah kode aksi audit jadi label, misal 'login_failed' -> 'Login Gagal'."""
    return AUDIT_ACTION_LABEL_DICT.get(action, action)

def get_audit_entity_label(entity_type):
    """Ubah nama tabel di audit log jadi label, misal 'access_entries' -> 'Data Link'."""
    return AUDIT_ENTITY_LABEL_DICT.get(entity_type, entity_type)

def get_user_status_label(status):
    # ubah code status akun jdi label contoh "active" -> "Aktif"
    return USER_STATUS_LABEL_DICT.get(status, status)