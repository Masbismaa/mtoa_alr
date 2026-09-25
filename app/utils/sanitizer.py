"""Bersihin input teks dari user biar aman dari XSS."""

import html
import re

import nh3

from app.utils.constants import MAX_TEXT_LENGTH

# karakter kontrol aneh (null byte dkk), tab & enter tetep dibiarin
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# jaga-jaga input yg di-encode berlapis
MAX_CLEAN_ROUND = 3

def sanitize_text(value, max_length=MAX_TEXT_LENGTH):
    """Buang semua tag HTML, karakter kontrol, spasi di ujung, terus potong sesuai max_length.

    Hasilnya teks polos. Pas ditampilin, Jinja2 tetep escape lagi (lapis kedua).
    """
    if value is None:
        return None

    cleaned_text = str(value)

    # buang tag HTML, ulang sampe hasilnya ga berubah lagi
    for _ in range(MAX_CLEAN_ROUND):
        next_text = html.unescape(nh3.clean(cleaned_text, tags=set()))
        if next_text == cleaned_text:
            break
        cleaned_text = next_text

    # buang karakter kontrol + spasi depan belakang
    cleaned_text = CONTROL_CHAR_PATTERN.sub("", cleaned_text).strip()
    return cleaned_text[:max_length]