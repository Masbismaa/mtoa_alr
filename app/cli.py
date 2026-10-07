"""Perintah CLI tambahan untuk aplikasi (dijalankan lewat: python -m flask --app run <perintah>)."""

import click
import time

def register_cli_commands(app):
    """Mendaftarkan semua perintah CLI custom ke aplikasi."""
    from app.services.auth_service import register_user
    from app.services.seed_service import seed_default_categories
    from app.utils.constants import ROLE_ADMIN
    from app.utils.exceptions import AuthError
    from app.extensions import db
    from app.models import User
    from app.services.user_service import change_user_role
    from app.utils.constants import ROLE_USER_ENTRY
    from app.utils.exceptions import ValidationError
    from app.utils.text_helper import normalize_email
    from app.services.link_monitor_service import build_run_summary_text, process_pending_monitor, recover_stale_monitor, run_monitor

    @app.cli.command("seed-categories")
    def seed_categories_command():
        """Mengisi kategori default (Web, Application, Network, General)."""
        created_count = seed_default_categories()
        click.echo(f"{created_count} kategori baru ditambahkan.")

    @app.cli.command("create-admin")
    @click.option("--email", prompt="Email admin")
    @click.option("--full-name", prompt="Nama lengkap")
    @click.option("--department", prompt="Departemen")
    @click.option("--job-title", prompt="Jabatan")
    @click.password_option("--password", prompt="Password")
    def create_admin_command(email, full_name, department, job_title, password):
        """Bikin akun Admin (satu-satunya cara bikin admin)."""
        # pake fungsi register yg sama, bedanya role-nya admin
        try:
            user = register_user(
                email=email,
                password=password,
                full_name=full_name,
                department=department,
                job_title=job_title,
                role=ROLE_ADMIN,
            )
        except AuthError as error:
            raise click.ClickException(str(error)) from error
        click.echo(f"Admin {user.email} berhasil dibuat.")

    def run_role_command(email, new_role):
        """Cari user dari email terus ganti role-nya (dipake set-admin & unset-admin)."""
        user = db.session.execute(db.select(User).filter_by(email=normalize_email(email))).scalar_one_or_none()
        if user is None:
            raise click.ClickException(f"User dengan email {email} tidak ditemukan")
        try:
            change_user_role(None, user, new_role)
        except ValidationError as error:
            raise click.ClickException(error.error_list[0]["message"]) from error
        return user

    @app.cli.command("set-admin")
    @click.option("--email", prompt="Email user")
    def set_admin_command(email):
        """Naikin user jadi Admin (cuma bisa lewat command)."""
        user = run_role_command(email, ROLE_ADMIN)
        click.echo(f"{user.email} sekarang Admin.")

    @app.cli.command("unset-admin")
    @click.option("--email", prompt="Email admin")
    def unset_admin_command(email):
        """Turunin Admin jadi User Entry. Admin aktif terakhir ga bisa diturunin."""
        user = run_role_command(email, ROLE_USER_ENTRY)
        click.echo(f"{user.email} sekarang User Entry.")

    @app.cli.command("check-links")
    def check_links_command():
        """Jalankan satu pemeriksaan manual, memakai kunci yang sama dengan worker."""
        try:
            click.echo(build_run_summary_text(run_monitor()))
        except ValidationError as error:
            raise click.ClickException(error.error_list[0]["message"]) from error

    @app.cli.command("monitor-worker")
    @click.option("--once", is_flag=True, help="Proses satu antrean lalu berhenti.")
    def monitor_worker_command(once):
        """Proses permintaan tombol admin; tidak membuat pemeriksaan terjadwal."""
        while True:
            try:
                counts = process_pending_monitor()
                if counts is not None:
                    click.echo(build_run_summary_text(counts))
            except Exception:
                if once:
                    raise click.ClickException("Pemeriksaan gagal; periksa layanan dan jaringan") from None
                click.echo("Pemeriksaan gagal; menunggu permintaan berikutnya.", err=True)
            if once:
                return
            db.session.remove()
            time.sleep(2)

    @app.cli.command("recover-link-monitor")
    def recover_link_monitor_command():
        """Cabut pemeriksaan macet yang tidak memberi progres selama lima menit."""
        click.echo("Pemeriksaan dicabut." if recover_stale_monitor() else "Tidak ada pemeriksaan macet.")

    @app.cli.command("cleanup-attachments")
    @click.option("--delete", is_flag=True, help="Hapus file yatim yang sudah lebih dari 24 jam.")
    def cleanup_attachments_command(delete):
        """Default hanya menampilkan jumlah file yatim; tidak menghapus file terdaftar."""
        from app.models import Attachment
        from app.services.attachment_service import get_upload_folder
        cutoff = time.time() - 86400
        count = 0
        paths = [path for path in get_upload_folder().iterdir()
                 if path.is_file() and not path.is_symlink() and path.stat().st_mtime < cutoff]
        for offset in range(0, len(paths), 500):
            batch = paths[offset:offset + 500]
            stored_names = set(db.session.scalars(db.select(Attachment.stored_filename).where(
                Attachment.stored_filename.in_([path.name for path in batch])
            )))
            for path in batch:
                if path.name in stored_names:
                    continue
                count += 1
                if delete:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        raise click.ClickException("Lampiran belum dapat dihapus; periksa izin folder") from None
        click.echo(f"{count} file yatim {'dihapus' if delete else 'ditemukan (belum dihapus)'}.")
