"""Helper kecil buat bikin query & baca parameter URL."""
from datetime import date
from sqlalchemy import or_
from app.utils.constants import MAX_SEARCH_KEYWORD_LENGTH

def escape_like_pattern(text):
    """Escape % dan _ biar dianggap huruf biasa pas dipake di LIKE."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

def build_keyword_filter(column_list, keyword):
    """Filter LIKE (ga peduli huruf besar/kecil) ke beberapa kolom sekaligus, % dan _ ga jadi wildcard."""
    like_pattern = f"%{escape_like_pattern(keyword)}%"
    return or_(*(column.ilike(like_pattern, escape="\\") for column in column_list))

def parse_positive_int(raw_value, default=None):
    """Ubah teks jadi angka > 0, kalau ga valid balikin default."""
    try:
        number = int(raw_value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default

def parse_date_arg(raw_value):
    """Ubah teks YYYY-MM-DD jadi date, kalau ga valid balikin None."""
    try:
        return date.fromisoformat(raw_value or "")
    except ValueError:
        return None

def clean_keyword_arg(raw_value):
    """Rapihin kata kunci search: buang spasi di ujung + potong kepanjangan."""
    return (raw_value or "").strip()[:MAX_SEARCH_KEYWORD_LENGTH]

def drop_empty_value(raw_dict):
    """Buang item yg kosong, dipake buat parameter filter di link pagination."""
    return {key: value for key, value in raw_dict.items() if value}