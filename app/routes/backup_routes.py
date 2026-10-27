"""Panel admin Backup & Restore: database & lampiran website dipisah, masing-masing bisa dibikin, diunduh, di-restore."""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import limiter
from app.security.role_guard import admin_required
from app.services.audit_service import log_audit
from app.services.backup_service import (
    BACKUP_ENTITY,
    BACKUP_KIND_DATABASE,
    BACKUP_KIND_WEBSITE,
    BACKUP_PREFIX_DICT,
    create_database_backup,
    create_website_backup,
    get_backup_path,
    list_backup,
    restore_database_backup,
    restore_website_backup,
)
from app.utils.constants import AUDIT_ACTION_EXPORT
from app.utils.exceptions import ValidationError
from app.utils.form_helper import flash_error_list

backup_bp = Blueprint("backup", __name__, url_prefix="/backups")

def check_kind(kind):
    """Jenis di URL cuma boleh database / website."""
    if kind not in BACKUP_PREFIX_DICT:
        abort(404)

@backup_bp.get("/")
@login_required
@admin_required
def index():
    return render_template(
        "pages/backup/index.html",
        page_title="Backup & Restore",
        database_backup_list=list_backup(BACKUP_KIND_DATABASE),
        website_backup_list=list_backup(BACKUP_KIND_WEBSITE),
        backup_folder=current_app.config["BACKUP_FOLDER"],
    )

@backup_bp.post("/<kind>/create")
@login_required
@admin_required
@limiter.limit("10 per hour")
def create(kind):
    check_kind(kind)
    try:
        create_backup = create_database_backup if kind == BACKUP_KIND_DATABASE else create_website_backup
        backup_path = create_backup(current_user)
    except ValidationError as error:
        flash_error_list(error.error_list)
    else:
        flash(f"Backup {backup_path.name} created", "success")
    return redirect(url_for("backup.index"))

@backup_bp.get("/<kind>/<name>/download")
@login_required
@admin_required
def download(kind, name):
    check_kind(kind)
    try:
        backup_path = get_backup_path(kind, name)
    except ValidationError:
        abort(404)
    # isinya data aplikasi, jadi tiap unduhan dicatat
    log_audit(AUDIT_ACTION_EXPORT, BACKUP_ENTITY, name, new_data_dict={"download": True}, user=current_user, is_commit=True)
    return send_file(backup_path, as_attachment=True, download_name=name)

@backup_bp.post("/<kind>/<name>/restore")
@login_required
@admin_required
@limiter.limit("5 per hour")
def restore(kind, name):
    check_kind(kind)
    try:
        if kind == BACKUP_KIND_DATABASE:
            safety_backup_path = restore_database_backup(name, current_user.email)
            message = f"Database restored from {name}. The data before the restore was saved as {safety_backup_path.name}"
        else:
            restored_count = restore_website_backup(name, current_user.email)
            message = f"Attachments restored from {name}: {restored_count} missing file(s) put back"
    except ValidationError as error:
        flash_error_list(error.error_list)
    else:
        flash(message, "success")
    return redirect(url_for("backup.index"))
