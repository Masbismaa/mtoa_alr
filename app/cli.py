"""Perintah CLI tambahan untuk aplikasi (dijalankan lewat: python -m flask --app run <perintah>)."""

import click


def register_cli_commands(app):
    """Mendaftarkan semua perintah CLI custom ke aplikasi."""
    from app.services.seed_service import seed_default_categories

    @app.cli.command("seed-categories")
    def seed_categories_command():
        """Mengisi kategori default (Web, Application, Network, General)."""
        created_count = seed_default_categories()
        click.echo(f"{created_count} kategori baru ditambahkan.")