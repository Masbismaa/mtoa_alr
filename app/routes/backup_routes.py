"""Panel admin Backup & Restore: bikin backup, unduh, dan restore dari file backup yg ada di server."""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import limiter
from app.security.role_guard import admin_required
from app.services.audit_service import log_audit
from app.services.backup_service import BACKUP_ENTITY, create_backup, get_backup_path, list_backup, restore_backup
from app.utils.constants import AUDIT_ACTION_EXPORT
from app.utils.exceptions import ValidationError
from app.utils.form_helper import flash_error_list

backup_bp = Blueprint("backup", __name__, url_prefix="/backups")

@backup_bp.get("/")
@login_required
@admin_required
def index():
    return render_template(
        "pages/backup/index.html",
        page_title="Backup & Restore",
        backup_list=list_backup(),
        backup_folder=current_app.config["BACKUP_FOLDER"],
    )

@backup_bp.post("/create")
@login_required
@admin_required
@limiter.limit("10 per hour")
def create():
    try:
        backup_path = create_backup(current_user)
    except ValidationError as error:
        flash_error_list(error.error_list)
    else:
        flash(f"Backup {backup_path.name} created", "success")
    return redirect(url_for("backup.index"))

@backup_bp.get("/<name>/download")
@login_required
@admin_required
def download(name):
    try:
        backup_path = get_backup_path(name)
    except ValidationError:
        abort(404)
    # isinya semua data aplikasi, jadi tiap unduhan dicatat
    log_audit(AUDIT_ACTION_EXPORT, BACKUP_ENTITY, name, new_data_dict={"download": True}, user=current_user, is_commit=True)
    return send_file(backup_path, as_attachment=True, download_name=name)

@backup_bp.post("/<name>/restore")
@login_required
@admin_required
@limiter.limit("5 per hour")
def restore(name):
    try:
        safety_backup_path = restore_backup(name, current_user.email)
    except ValidationError as error:
        flash_error_list(error.error_list)
    else:
        flash(f"Restored from {name}. The data before the restore was saved as {safety_backup_path.name}", "success")
    return redirect(url_for("backup.index"))
