"""Helper olah teks yg dipake di banyak tempat."""

from app.utils.constants import ROLE_LABEL_DICT

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

def get_initials(full_name, max_letter_count=2):
    """Ambil huruf depan nama buat avatar, misal 'Bisma Prasetya' -> 'BP'."""
    word_list = [word for word in (full_name or "").split() if word]
    if not word_list:
        return "?"
    return "".join(word[0] for word in word_list[:max_letter_count]).upper()

def get_role_label(role):
    """Ubah kode role jadi label yg enak dibaca, misal 'user_entry' -> 'User Entry'."""
    return ROLE_LABEL_DICT.get(role, role)