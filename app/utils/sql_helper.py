"""Helper untuk kebutuhan SQL yang dipakai ulang oleh beberapa model (DRY)."""


def build_sql_in_list(value_list):
    """List string jadi isi SQL IN. Cuma buat konstanta internal, JANGAN buat input user."""
    return ", ".join(f"'{value}'" for value in value_list)