"""Helper kecil buat bikin query & baca parameter URL."""
def escape_like_pattern(text):
    """Escape % dan _ biar dianggap huruf biasa pas dipake di LIKE."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

def parse_positive_int(raw_value, default=None):
    """Ubah teks jadi angka > 0, kalau ga valid balikin default."""
    try:
        number = int(raw_value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default