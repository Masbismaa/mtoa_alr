"""Unit test untuk memastikan dokumen docs/requirements.md lengkap dan valid."""

import re
from pathlib import Path

import pytest

# Lokasi file requirement, dihitung dari posisi file test ini
REQUIREMENTS_PATH = Path(__file__).resolve().parent.parent / "docs" / "requirements.md"

# Daftar ID requirement yang wajib ada: SR-01 sampai SR-17
EXPECTED_ID_LIST = [f"SR-{number:02d}" for number in range(1, 18)]


@pytest.fixture(scope="module")
def requirements_text():
    """Membaca isi requirements.md SEKALI untuk semua test (hindari double read)."""
    return REQUIREMENTS_PATH.read_text(encoding="utf-8")


def test_requirements_file_exists():
    """Positive: file docs/requirements.md harus ada."""
    assert REQUIREMENTS_PATH.is_file(), "docs/requirements.md belum dibuat"


def test_requirements_contains_all_sr_ids(requirements_text):
    """Positive: semua ID SR-01 sampai SR-17 harus tercantum."""
    missing_id_list = [req_id for req_id in EXPECTED_ID_LIST if req_id not in requirements_text]
    assert missing_id_list == [], f"SR belum ada: {missing_id_list}"


def test_requirements_has_no_unknown_sr_ids(requirements_text):
    """Negative: tidak boleh ada ID SR di luar daftar resmi (misal SR-18)."""
    found_id_set = set(re.findall(r"SR-\d{2}", requirements_text))
    unknown_id_set = found_id_set - set(EXPECTED_ID_LIST)
    assert unknown_id_set == set(), f"SR tidak dikenal: {unknown_id_set}"


def test_requirements_contains_mandatory_sections(requirements_text):
    """Positive: bagian wajib (RBAC, Group, Audit Log, dll) harus dibahas di dokumen."""
    section_list = ["RBAC", "Group", "Audit Log", "Security", "Sidebar", "Customizer", "Dark Mode"]
    missing_section_list = [section for section in section_list if section not in requirements_text]
    assert missing_section_list == [], f"Bagian belum ada: {missing_section_list}"