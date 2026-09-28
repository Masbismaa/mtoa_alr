"""Test format ukuran file."""
from app.utils.text_helper import format_file_size
def test_format_file_size():
    """Positive: B, KB, MB kebaca rapi."""
    assert format_file_size(500) == "500 B"
    assert format_file_size(2048) == "2.0 KB"
    assert format_file_size(3 * 1024 * 1024) == "3.0 MB"
    assert format_file_size(None) == "-"