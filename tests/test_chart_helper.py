"""Test helper grafik mini dashboard."""
from app.utils.chart_helper import build_bar_list, build_sparkline, calculate_change_percent, calculate_percent


def test_build_sparkline_makes_line_and_area():
    """Positive: titik tertinggi nempel atas, path area ditutup ke bawah."""
    chart = build_sparkline([0, 5, 10], width=100, height=40, padding=0)
    assert chart["line_path"] == "M0.0,40.0 L50.0,20.0 L100.0,0.0"
    assert chart["area_path"].endswith("L100.0,40 L0.0,40 Z")


def test_build_sparkline_empty_data():
    """Negative: data kosong / nol semua ga bikin error bagi nol."""
    assert build_sparkline([])["line_path"].startswith("M")
    assert build_sparkline([0, 0])["line_path"]


def test_build_bar_list():
    """Positive: batang paling tinggi = 100%."""
    assert build_bar_list([1, 4, 2]) == [
        {"value": 1, "height_percent": 25},
        {"value": 4, "height_percent": 100},
        {"value": 2, "height_percent": 50},
    ]
    assert build_bar_list([0, 0])[0]["height_percent"] == 0


def test_calculate_percent_and_change():
    """Positive & negative: persen aman dari bagi nol."""
    assert calculate_percent(1, 4) == 25
    assert calculate_percent(3, 0) == 0
    assert calculate_change_percent(15, 10) == 50
    assert calculate_change_percent(5, 10) == -50
    assert calculate_change_percent(5, 0) is None
