"""Helper olah teks yg dipake di banyak tempat."""


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