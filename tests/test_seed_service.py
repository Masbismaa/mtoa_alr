"""Unit test untuk seed kategori default (SR-01)."""

from app.extensions import db
from app.models import Category
from app.services.seed_service import seed_default_categories
from app.utils.constants import DEFAULT_CATEGORY_LIST


def test_seed_default_categories_creates_all(app):
    """Positive: seed pertama menambahkan semua kategori default."""
    created_count = seed_default_categories()
    name_list = db.session.execute(db.select(Category.name)).scalars().all()
    assert created_count == len(DEFAULT_CATEGORY_LIST)
    assert sorted(name_list) == sorted(item["name"] for item in DEFAULT_CATEGORY_LIST)


def test_seed_default_categories_is_idempotent(app):
    """Negative: seed kedua kali tidak boleh membuat data ganda."""
    seed_default_categories()
    second_created_count = seed_default_categories()
    total_count = db.session.execute(db.select(db.func.count(Category.id))).scalar()
    assert second_created_count == 0
    assert total_count == len(DEFAULT_CATEGORY_LIST)


def test_seed_categories_cli_command(app):
    """Positive: perintah CLI seed-categories berjalan tanpa error."""
    runner = app.test_cli_runner()
    result = runner.invoke(args=["seed-categories"])
    assert result.exit_code == 0
    assert "4 kategori baru ditambahkan" in result.output