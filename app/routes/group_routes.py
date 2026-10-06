"""Route group: daftar, bikin, detail, edit, hapus, anggota, link."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from app.extensions import limiter
from app.schemas.group_schema import GroupForm
from app.security.access_policy import is_group_owner
from app.services.group_service import (
    accept_invitation,
    add_group_entry,
    can_remove_group_entry,
    create_group,
    decline_invitation,
    delete_group,
    get_member_group,
    get_own_invitation,
    invite_member,
    leave_group,
    list_addable_entry,
    list_pending_invitation,
    list_user_group,
    remove_group_entry,
    remove_member,
    update_group,
)
from app.utils.exceptions import ValidationError
from app.utils.form_helper import flash_error_list, read_form_data
from app.utils.request_helper import get_current_user

groups_bp = Blueprint("groups", __name__, url_prefix="/groups")

GROUP_FIELD_NAME_LIST = ["name", "description"]


def get_group_or_404(user, group_id):
    """Bukan anggota aktif -> 404."""
    group = get_member_group(user, group_id)
    if group is None:
        abort(404)
    return group


def require_group_owner(user, group):
    """Anggota biasa -> 403."""
    if not is_group_owner(user, group):
        abort(403)


def render_group_form(form, page_title, cancel_url):
    """Render form bikin/edit group."""
    return render_template("pages/groups/form.html", form=form, page_title=page_title, cancel_url=cancel_url)


@groups_bp.get("/")
@login_required
def index():
    """Daftar group + undangan yg nunggu."""
    user = get_current_user()
    return render_template(
        "pages/groups/index.html",
        page_title="Groups",
        group_list=list_user_group(user),
        invitation_list=list_pending_invitation(user),
    )


@groups_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    """Bikin group baru."""
    form = GroupForm()
    if form.validate_on_submit():
        try:
            group = create_group(get_current_user(), read_form_data(form, GROUP_FIELD_NAME_LIST))
        except ValidationError as error:
            flash_error_list(error.error_list)
        else:
            flash(f'Group "{group.name}" berhasil dibuat', "success")
            return redirect(url_for("groups.detail", group_id=group.id))
    return render_group_form(form, "Buat Group", url_for("groups.index"))


@groups_bp.get("/<int:group_id>")
@login_required
def detail(group_id):
    """Detail group: link & anggota."""
    user = get_current_user()
    group = get_group_or_404(user, group_id)
    return render_template(
        "pages/groups/detail.html",
        page_title="Group",
        group=group,
        addable_entry_list=list_addable_entry(user, group),
        can_remove_group_entry=can_remove_group_entry,
    )


@groups_bp.route("/<int:group_id>/edit", methods=["GET", "POST"])
@login_required
def edit(group_id):
    """Edit nama/deskripsi, cuma pemilik."""
    user = get_current_user()
    group = get_group_or_404(user, group_id)
    require_group_owner(user, group)
    form = GroupForm(obj=group)
    if form.validate_on_submit():
        try:
            update_group(user, group, read_form_data(form, GROUP_FIELD_NAME_LIST))
        except ValidationError as error:
            flash_error_list(error.error_list)
        else:
            flash("Group berhasil diperbarui", "success")
            return redirect(url_for("groups.detail", group_id=group.id))
    return render_group_form(form, "Edit Group", url_for("groups.detail", group_id=group.id))


@groups_bp.post("/<int:group_id>/delete")
@login_required
def delete(group_id):
    """Hapus group, cuma pemilik."""
    user = get_current_user()
    group = get_group_or_404(user, group_id)
    require_group_owner(user, group)
    group_name = group.name
    delete_group(user, group)
    flash(f'Group "{group_name}" berhasil dihapus', "success")
    return redirect(url_for("groups.index"))


@groups_bp.post("/<int:group_id>/members")
@login_required
@limiter.limit("20 per minute")
def invite(group_id):
    """Undang anggota lewat email."""
    user = get_current_user()
    group = get_group_or_404(user, group_id)
    require_group_owner(user, group)
    email = request.form.get("email", "")
    try:
        invite_member(user, group, email)
    except ValidationError as error:
        flash_error_list(error.error_list)
    else:
        flash(f"Undangan terkirim ke {email.strip().lower()}", "success")
    return redirect(url_for("groups.detail", group_id=group.id))


@groups_bp.post("/<int:group_id>/members/<int:member_id>/remove")
@login_required
def remove_group_member(group_id, member_id):
    """Keluarin anggota / batalin undangan."""
    user = get_current_user()
    group = get_group_or_404(user, group_id)
    require_group_owner(user, group)
    try:
        remove_member(user, group, member_id)
    except ValidationError as error:
        flash_error_list(error.error_list)
    else:
        flash("Anggota berhasil dikeluarkan", "success")
    return redirect(url_for("groups.detail", group_id=group.id))


@groups_bp.post("/<int:group_id>/leave")
@login_required
def leave(group_id):
    """Keluar dari group."""
    user = get_current_user()
    group = get_group_or_404(user, group_id)
    try:
        leave_group(user, group)
    except ValidationError as error:
        flash_error_list(error.error_list)
        return redirect(url_for("groups.detail", group_id=group.id))
    flash("Kamu sudah keluar dari group", "info")
    return redirect(url_for("groups.index"))


@groups_bp.post("/invitations/<int:member_id>/accept")
@login_required
def accept(member_id):
    """Terima undangan."""
    user = get_current_user()
    invitation = get_own_invitation(user, member_id)
    if invitation is None:
        abort(404)
    accept_invitation(user, invitation)
    flash("Undangan diterima, selamat bergabung!", "success")
    return redirect(url_for("groups.detail", group_id=invitation.group_id))


@groups_bp.post("/invitations/<int:member_id>/decline")
@login_required
def decline(member_id):
    """Tolak undangan."""
    user = get_current_user()
    invitation = get_own_invitation(user, member_id)
    if invitation is None:
        abort(404)
    decline_invitation(user, invitation)
    flash("Undangan ditolak", "info")
    return redirect(url_for("groups.index"))


@groups_bp.post("/<int:group_id>/entries")
@login_required
def add_entry(group_id):
    """Tambah link yg udah ada ke group."""
    user = get_current_user()
    group = get_group_or_404(user, group_id)
    try:
        add_group_entry(user, group, request.form.get("entry_id"))
    except ValidationError as error:
        flash_error_list(error.error_list)
    else:
        flash("Link berhasil ditambahkan ke group", "success")
    return redirect(url_for("groups.detail", group_id=group.id))


@groups_bp.post("/<int:group_id>/entries/<int:group_entry_id>/remove")
@login_required
def remove_entry(group_id, group_entry_id):
    """Cabut link dari group."""
    user = get_current_user()
    group = get_group_or_404(user, group_id)
    try:
        remove_group_entry(user, group, group_entry_id)
    except ValidationError as error:
        flash_error_list(error.error_list)
    else:
        flash("Link dicabut dari group", "success")
    return redirect(url_for("groups.detail", group_id=group.id))
