"""Select Screen ala SAP: baca kriteria dari URL (banyak nilai, sertakan/kecualikan, wildcard *) & ubah jadi filter SQL.
Dipake bareng sama Daftar Link, Users, Audit Logs, dan Groups."""
from collections import namedtuple
from sqlalchemy import and_, not_, or_
from app.utils.constants import MAX_SEARCH_KEYWORD_LENGTH, SELECTION_EXCLUDE_SUFFIX, SELECTION_MAX_VALUE_COUNT
from app.utils.datetime_helper import build_utc_range_from_local_date
from app.utils.query_helper import build_keyword_filter, parse_date_arg, parse_positive_int

SELECTION_TEXT = "text"
SELECTION_CHOICE = "choice"
SELECTION_DATE_RANGE = "date_range"
QUICK_SEARCH_KEY = "q"

# satu isian di panel Kriteria Pencarian. option_list cuma buat choice, from_key/to_key cuma buat date_range
SelectionField = namedtuple(
    "SelectionField",
    ["key", "label", "kind", "option_list", "placeholder", "from_key", "to_key"],
    defaults=[None, "", None, None],
)

# isian teks: nilai yg disertakan (cocok salah satu) & yg dikecualikan (ga boleh cocok satu pun)
TextSelection = namedtuple("TextSelection", ["include_list", "exclude_list"])

def text_field(key, label, placeholder=""):
    """Isian teks: bisa wildcard * dan Multi Selection (sertakan/kecualikan)."""
    return SelectionField(key, label, SELECTION_TEXT, placeholder=placeholder)

def choice_field(key, label, option_list):
    """Isian pilihan: centang lebih dari satu. option_list = [(nilai, label)]."""
    return SelectionField(key, label, SELECTION_CHOICE, option_list=[(str(value), text) for value, text in option_list])

def date_range_field(key, label, from_key=None, to_key=None):
    """Isian rentang tanggal dari–sampai. Nama parameter default: <key>_from & <key>_to."""
    return SelectionField(key, label, SELECTION_DATE_RANGE, from_key=from_key or f"{key}_from", to_key=to_key or f"{key}_to")

def clean_value_list(raw_value_list):
    """Nilai dari URL: dirapihin, yg kosong & dobel dibuang, jumlah & panjangnya dibatesin."""
    value_list = []
    for raw_value in raw_value_list:
        value = (raw_value or "").strip()[:MAX_SEARCH_KEYWORD_LENGTH]
        if value and value not in value_list:
            value_list.append(value)
    return value_list[:SELECTION_MAX_VALUE_COUNT]

def read_text_selection(args, key):
    """Baca isian teks: ?title=a&title=b&title__not=c."""
    return TextSelection(clean_value_list(args.getlist(key)), clean_value_list(args.getlist(key + SELECTION_EXCLUDE_SUFFIX)))

def read_choice_selection(args, key, allowed_value_list):
    """Baca isian pilihan, nilai yg ga dikenal dicuekin."""
    return [value for value in clean_value_list(args.getlist(key)) if value in allowed_value_list]

def read_id_selection(args, key):
    """Baca isian pilihan berupa id angka (misal kategori)."""
    id_list = [parse_positive_int(value) for value in clean_value_list(args.getlist(key))]
    return [value for value in id_list if value is not None]

def read_date_range(args, field):
    """Baca rentang tanggal, yg formatnya ngaco jadi None."""
    return parse_date_arg(args.get(field.from_key)), parse_date_arg(args.get(field.to_key))

def build_text_selection_filter(column_list, selection):
    """Kondisi SQL isian teks. None kalau isiannya kosong."""
    condition_list = []
    if selection.include_list:
        condition_list.append(or_(*(build_keyword_filter(column_list, value) for value in selection.include_list)))
    condition_list.extend(not_(build_keyword_filter(column_list, value)) for value in selection.exclude_list)
    return and_(*condition_list) if condition_list else None

def build_date_range_filter(column, date_from, date_to):
    """Kondisi SQL rentang tanggal (tanggal WIB, sampai akhir hari). None kalau dua-duanya kosong."""
    start_at, end_at = build_utc_range_from_local_date(date_from, date_to)
    condition_list = []
    if start_at:
        condition_list.append(column >= start_at)
    if end_at:
        condition_list.append(column < end_at)
    return and_(*condition_list) if condition_list else None

def apply_condition_list(query, condition_list):
    """Tempel kondisi ke query, yg None dilewatin."""
    return query.where(*(condition for condition in condition_list if condition is not None))

def list_field_key(field):
    """Nama parameter URL yg dipake satu isian."""
    if field.kind == SELECTION_TEXT:
        return [field.key, field.key + SELECTION_EXCLUDE_SUFFIX]
    if field.kind == SELECTION_DATE_RANGE:
        return [field.from_key, field.to_key]
    return [field.key]

def build_selection_query_dict(args, field_list):
    """Kriteria yg lagi kepake, dibawa ke link halaman berikutnya & export. Cuma parameter yg dikenal."""
    key_list = [QUICK_SEARCH_KEY] + [key for field in field_list for key in list_field_key(field)]
    query_dict = {}
    for key in key_list:
        value_list = clean_value_list(args.getlist(key))
        if value_list:
            query_dict[key] = value_list
    return query_dict

def describe_selection(args, field_list):
    """Kriteria dalam bentuk teks (buat sheet Info di export & audit log), misal 'Judul "portal*" kecuali "*test*"'."""
    text_list = []
    keyword = clean_value_list([args.get(QUICK_SEARCH_KEY)])
    if keyword:
        text_list.append(f'Kata kunci "{keyword[0]}"')
    for field in field_list:
        if field.kind == SELECTION_TEXT:
            selection = read_text_selection(args, field.key)
            part_list = [", ".join(f'"{value}"' for value in selection.include_list)] if selection.include_list else []
            if selection.exclude_list:
                part_list.append("kecuali " + ", ".join(f'"{value}"' for value in selection.exclude_list))
            if part_list:
                text_list.append(f"{field.label} {' '.join(part_list)}")
        elif field.kind == SELECTION_CHOICE:
            label_dict = dict(field.option_list)
            label_list = [label_dict[value] for value in clean_value_list(args.getlist(field.key)) if value in label_dict]
            if label_list:
                text_list.append(f"{field.label} {', '.join(label_list)}")
        else:
            date_from, date_to = read_date_range(args, field)
            if date_from or date_to:
                from_text = date_from.strftime("%d-%m-%Y") if date_from else "awal"
                to_text = date_to.strftime("%d-%m-%Y") if date_to else "sekarang"
                text_list.append(f"{field.label} {from_text} s/d {to_text}")
    return text_list
