"""Perintah CLI tambahan untuk aplikasi (dijalankan lewat: python -m flask --app run <perintah>)."""

import click

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
    from app.services.link_check_service import check_all_entry_status
    from app.utils.constants import LINK_STATUS_DOWN, LINK_STATUS_UNKNOWN, LINK_STATUS_UP

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
        """Cek status semua link sekaligus. Bisa dijadwalin tiap pagi (Task Scheduler / cron)."""
        click.echo("Ngecek semua link, tunggu sebentar...")
        status_counter = check_all_entry_status()
        total_count = sum(status_counter.values())
        click.echo(
            f"Selesai, {total_count} link dicek: {status_counter[LINK_STATUS_UP]} aktif, "
            f"{status_counter[LINK_STATUS_DOWN]} tidak aktif, {status_counter[LINK_STATUS_UNKNOWN]} belum bisa dicek."
        )