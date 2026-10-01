"""Helper grafik mini (SVG) buat dashboard. Ga pake library chart, cukup hitung titiknya di Python."""


def build_sparkline(value_list, width=200, height=48, padding=4):
    """Ubah deret angka jadi path SVG garis + area di bawahnya."""
    value_list = value_list or [0]
    max_value = max(value_list) or 1
    step = width / max(len(value_list) - 1, 1)
    point_list = [
        (round(index * step, 2), round(height - padding - (value / max_value) * (height - 2 * padding), 2))
        for index, value in enumerate(value_list)
    ]
    line_path = "M" + " L".join(f"{x},{y}" for x, y in point_list)
    area_path = f"{line_path} L{point_list[-1][0]},{height} L{point_list[0][0]},{height} Z"
    return {"line_path": line_path, "area_path": area_path, "width": width, "height": height}


def build_bar_list(value_list):
    """Tinggi tiap batang dalam persen (batang paling tinggi = 100)."""
    max_value = max(value_list, default=0) or 1
    return [{"value": value, "height_percent": round(value / max_value * 100)} for value in value_list]


def calculate_percent(part, total):
    """Persentase bulat, aman kalau total 0."""
    return round(part / total * 100) if total else 0


def calculate_change_percent(current, previous):
    """Naik/turun berapa persen dibanding periode sebelumnya. None kalau sebelumnya 0 (ga bisa dibandingin)."""
    if not previous:
        return None
    return round((current - previous) / previous * 100)
