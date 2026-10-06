"""Download lampiran. Wajib login + boleh liat data induknya."""
from flask import Blueprint, abort, send_file
from flask_login import login_required

from app.services.attachment_service import get_stored_file_path, get_visible_attachment
from app.utils.request_helper import get_current_user

attachments_bp = Blueprint("attachments", __name__, url_prefix="/attachments")

@attachments_bp.get("/<int:attachment_id>")
@login_required
def download(attachment_id):
    """Download lampiran, selalu sebagai file (ga dibuka langsung di browser)."""
    attachment = get_visible_attachment(get_current_user(), attachment_id)
    if attachment is None:
        abort(404)

    file_path = get_stored_file_path(attachment.stored_filename)
    if not file_path.is_file():
        abort(404)

    response = send_file(
        file_path,
        mimetype=attachment.content_type,
        as_attachment=True,
        download_name=attachment.original_filename,
        max_age=0,
    )
    # browser ga boleh nebak-nebak tipe file + jangan disimpen di cache
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response