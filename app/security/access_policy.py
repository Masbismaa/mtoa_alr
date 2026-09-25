"""Aturan hak akses data link."""
from sqlalchemy import or_

from app.models import AccessEntry
from app.utils.constants import ROLE_ADMIN, VISIBILITY_PUBLIC

def is_entry_owner(user, entry):
    """True kalau user yg bikin data ini."""
    return entry.user_id == user.id

def can_view_entry(user, entry):
    """Boleh liat: punya sendiri, atau data Public. Private orang lain ga keliatan (admin juga)."""
    return is_entry_owner(user, entry) or entry.visibility == VISIBILITY_PUBLIC

def can_edit_entry(user, entry):
    """Boleh ubah/hapus: punya sendiri, atau admin untuk data Public."""
    if is_entry_owner(user, entry):
        return True
    return user.role == ROLE_ADMIN and entry.visibility == VISIBILITY_PUBLIC

def build_visible_entry_filter(user):
    """Filter query: cuma data yg boleh dilihat user ini (sama persis kayak can_view_entry)."""
    return or_(AccessEntry.user_id == user.id, AccessEntry.visibility == VISIBILITY_PUBLIC)