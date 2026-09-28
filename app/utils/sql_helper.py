"""Helper untuk kebutuhan SQL yang dipakai ulang oleh beberapa model (DRY)."""


def build_sql_in_list(value_list):
    """Mengubah list string menjadi format isi SQL IN.

    Contoh: ["admin", "user_entry"] -> "'admin', 'user_entry'"

    PENTING: hanya untuk konstanta internal di constants.py,
    JANGAN dipakai untuk input dari user (risiko SQL Injection).
    """
    return ", ".join(f"'{value}'" for value in value_list)