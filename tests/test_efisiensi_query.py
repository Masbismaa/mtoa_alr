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
