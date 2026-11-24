"""Menu Administration › Manage: Admin mindahin folder simpan lampiran & backup."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import limiter
from app.security.role_guard import admin_required
from app.services.storage_service import STORAGE_NAME_LIST, get_storage_folder, move_storage_folder
from app.utils.exceptions import ValidationError
from app.utils.form_helper import flash_error_list

storage_bp = Blueprint("storage", __name__, url_prefix="/manage")

@storage_bp.get("/")
@login_required
@admin_required
def index():
    return render_template(
        "pages/storage/index.html",
        page_title="Manage",
        folder_dict={name: str(get_storage_folder(name)) for name in STORAGE_NAME_LIST},
    )

@storage_bp.post("/<name>/move")
@login_required
@admin_required
@limiter.limit("10 per hour")
def move(name):
    if name not in STORAGE_NAME_LIST:
        abort(404)
    try:
        moved_count = move_storage_folder(name, request.form.get("path"), current_user)
    except ValidationError as error:
        flash_error_list(error.error_list)
    else:
        flash(f"Folder moved: {moved_count} item(s) copied to the new folder", "success")
    return redirect(url_for("storage.index"))
