"""Helper kecil buat bikin query & baca parameter URL."""
from datetime import date
from sqlalchemy import func, or_
from app.utils.constants import MAX_SEARCH_KEYWORD_LENGTH, SEARCH_WILDCARD

def escape_like_pattern(text):
    """Escape % dan _ biar dianggap huruf biasa pas dipake di LIKE."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

def build_like_pattern(keyword):
    """Kata kunci jadi pola LIKE. Tanpa * = mengandung kata itu. Pake * ala SAP: ad* = diawali ad, *ad = diakhiri ad, a*d = a...d.
    % dan _ yg diketik user tetep dianggap huruf biasa."""
    escaped_keyword = escape_like_pattern(keyword)
    if SEARCH_WILDCARD not in keyword:
        return f"%{escaped_keyword}%"
    return escaped_keyword.replace(SEARCH_WILDCARD, "%")

def build_keyword_filter(column_list, keyword):
    """Filter LIKE (ga peduli huruf besar/kecil) ke beberapa kolom sekaligus. Kolom kosong (NULL) dianggap teks kosong."""
    like_pattern = build_like_pattern(keyword)
    return or_(*(func.coalesce(column, "").ilike(like_pattern, escape="\\") for column in column_list))

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
