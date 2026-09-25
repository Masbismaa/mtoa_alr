"""Perintah CLI tambahan untuk aplikasi (dijalankan lewat: python -m flask --app run <perintah>)."""

import click

def register_cli_commands(app):
    """Mendaftarkan semua perintah CLI custom ke aplikasi."""
    from app.services.auth_service import register_user
    from app.services.seed_service import seed_default_categories
    from app.utils.constants import ROLE_ADMIN
    from app.utils.exceptions import AuthError

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