"""Bersihin input teks dari user biar aman dari XSS."""
import html
import re

import nh3
from markupsafe import Markup

from app.utils.constants import (
    ALLOWED_URL_SCHEME_SET,
    MAX_RICH_TEXT_LENGTH,
    MAX_TEXT_LENGTH,
    RICH_TEXT_ALLOWED_TAG_SET,
)

# karakter kontrol aneh (null byte dkk), tab & enter tetep dibiarin
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# jaga-jaga input yg di-encode berlapis (&amp;lt;script&amp;gt;)
MAX_CLEAN_ROUND = 3

# atribut yg boleh di editor: cuma href di link
RICH_TEXT_ALLOWED_ATTRIBUTE_DICT = {"a": {"href"}}

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

def sanitize_rich_text(value, max_length=MAX_RICH_TEXT_LENGTH):
    """Bersihin HTML dari editor teks: cuma tag format yg diizinin, link cuma http/https.

    Link otomatis dikasih rel="noopener noreferrer".
    """
    if not value:
        return ""
    return nh3.clean(
        str(value)[:max_length],
        tags=RICH_TEXT_ALLOWED_TAG_SET,
        attributes=RICH_TEXT_ALLOWED_ATTRIBUTE_DICT,
        url_schemes=ALLOWED_URL_SCHEME_SET,
        link_rel="noopener noreferrer",
    ).strip()

def get_plain_text(html_text):
    """Ambil teksnya doang dari HTML (buat ngecek isi editor kosong atau nggak)."""
    if not html_text:
        return ""
    return html.unescape(nh3.clean(str(html_text), tags=set())).strip()

def render_rich_text(value):
    """Filter template: bersihin ulang HTML editor terus tandain aman buat ditampilin."""
    return Markup(sanitize_rich_text(value))