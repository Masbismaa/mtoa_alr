"""Batas query dan visibilitas saat jumlah kategori/link bertambah."""
from datetime import date, datetime, timezone
from sqlalchemy import event

from app.extensions import db
from app.models import AccessEntry, Category, GroupEntry, GroupEntryViewer, GroupMember
from app.services.access_entry_service import list_selected_category_id
from app.services.category_service import build_forum_row_list
from app.services.dashboard_service import count_created_by_local_date
from app.services.group_service import count_visible_group_entries, create_group
from app.utils.constants import GROUP_MEMBER_STATUS_ACTIVE, GROUP_ROLE_MEMBER, VISIBILITY_PRIVATE


def count_queries(callback):
    statements = []
    def record(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)
    event.listen(db.engine, "before_cursor_execute", record)
    try:
        result = callback()
    finally:
        event.remove(db.engine, "before_cursor_execute", record)
    return result, statements


def test_forum_query_count_does_not_grow_per_category(app, registered_user, other_user):
    for number in range(40):
        category = Category(name=f"Category {number}")
        db.session.add(category)
        db.session.flush()
        db.session.add_all([
            AccessEntry(user_id=registered_user.id, category_id=category.id, title="Visible", visibility=VISIBILITY_PRIVATE),
            AccessEntry(user_id=other_user.id, category_id=category.id, title="Hidden", visibility=VISIBILITY_PRIVATE),
        ])
    db.session.commit()
    rows, statements = count_queries(lambda: build_forum_row_list(registered_user))
    assert len(rows) == 40
    assert len(statements) <= 4
    assert all(row["entry_count"] == 1 and row["latest_entry"].title == "Visible" for row in rows)


def test_category_selection_reads_tree_once(app, category_dict):
    parent = category_dict["Web"]
    child = Category(parent_id=parent.id, name="Child")
    db.session.add(child)
    db.session.commit()
    parent_id, child_id = parent.id, child.id
    ids, statements = count_queries(lambda: list_selected_category_id([parent_id, child_id, parent_id, 999999]))
    assert ids == [parent_id, child_id]
    assert len(statements) == 1


def test_group_counts_use_one_query_and_keep_viewer_permissions(app, registered_user, other_user, category_dict):
    group = create_group(other_user, {"name": "Restricted"})
    group.member_list.append(GroupMember(user_id=registered_user.id, role=GROUP_ROLE_MEMBER, status=GROUP_MEMBER_STATUS_ACTIVE))
    for number in range(20):
        entry = AccessEntry(user_id=other_user.id, category_id=category_dict["Web"].id, title=str(number))
        shared = GroupEntry(access_entry=entry, user_id=other_user.id, is_restricted=True)
        if number == 0:
            shared.viewer_list.append(GroupEntryViewer(user_id=registered_user.id))
        group.group_entry_list.append(shared)
    db.session.commit()
    db.session.refresh(group)
    db.session.refresh(registered_user)
    counts, statements = count_queries(lambda: count_visible_group_entries(registered_user, [group]))
    assert counts == {group.id: 1}
    assert len(statements) == 1
    assert count_visible_group_entries(other_user, [group]) == {group.id: 20}


def test_daily_counts_respect_wib_midnight(app, registered_user, category_dict):
    for hour, minute in [(16, 59), (17, 0)]:
        db.session.add(AccessEntry(user_id=registered_user.id, category_id=category_dict["Web"].id,
                                  title=f"{hour}:{minute}", created_at=datetime(2026, 10, 1, hour, minute, tzinfo=timezone.utc)))
    db.session.commit()
    counts = count_created_by_local_date(AccessEntry.created_at, AccessEntry.user_id == registered_user.id,
                                        [date(2026, 10, 1), date(2026, 10, 2)])
    assert counts == [1, 1]


def test_category_label_reads_tree_once_per_request(app, category_dict):
    """Positive: label kategori bertingkat di dalam request cuma 1 query, berapa pun kedalamannya."""
    from app.services.category_service import build_category_label

    parent = category_dict["Web"]
    level_two = Category(parent_id=parent.id, name="SAP")
    db.session.add(level_two)
    db.session.flush()
    level_three = Category(parent_id=level_two.id, name="Modul FI")
    db.session.add(level_three)
    db.session.commit()
    level_three_id = level_three.id
    db.session.expunge_all()
    with app.test_request_context("/"):
        category = db.session.get(Category, level_three_id)
        label, statements = count_queries(lambda: build_category_label(category))
    assert label == "Web › SAP › Modul FI"
    assert len(statements) == 1


def test_attachment_count_without_loading_rows(app, registered_user, category_dict):
    """Positive: jumlah lampiran di tabel dihitung SQL, baris lampiran ga ikut diambil."""
    from app.models import Attachment
    from app.services.access_entry_service import search_visible_entries

    entry = AccessEntry(user_id=registered_user.id, category_id=category_dict["Web"].id, title="Berlampiran")
    db.session.add(entry)
    db.session.flush()
    for number in range(3):
        db.session.add(Attachment(access_entry_id=entry.id, user_id=registered_user.id, original_filename="a.txt",
                                  stored_filename=f"file{number}.txt", content_type="text/plain", file_size=1))
    db.session.commit()
    db.session.expire_all()
    db.session.refresh(registered_user)
    pagination, statements = count_queries(lambda: search_visible_entries(registered_user))
    assert [item.attachment_count for item in pagination.items] == [3]
    # hitung total halaman + ambil baris, ga ada query tambahan buat lampiran
    assert len(statements) == 2


def test_group_member_and_invitation_counts(app, registered_user, other_user):
    """Positive: jumlah anggota aktif & undangan dihitung SQL (undangan ga ikut dihitung anggota)."""
    from app.services.group_service import count_active_member, count_pending_invitation, invite_member

    group = create_group(other_user, {"name": "Tim"})
    invite_member(other_user, group, registered_user.email)
    assert count_active_member([group]) == {group.id: 1}
    assert count_pending_invitation(registered_user) == 1
    assert count_active_member([]) == {}
