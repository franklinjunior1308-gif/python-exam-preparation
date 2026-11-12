from decimal import Decimal

from app.domain.money import estimate_total_cents, labor_total_cents, line_total_cents


def test_line_total_rounds_half_up_exactly():
    assert line_total_cents(Decimal("0.5"), 333) == 167  # 166.5 -> 167
    assert line_total_cents(Decimal("2"), 1050) == 2100
    assert line_total_cents(Decimal("1.333"), 100) == 133  # 133.3 -> 133
    assert line_total_cents(Decimal("0.001"), 499) == 0


def test_labor_uses_minutes_and_an_hourly_rate():
    assert labor_total_cents(60, 120_000) == 120_000
    assert labor_total_cents(90, 120_000) == 180_000
    assert labor_total_cents(1, 100) == 2  # 1.666... -> 2
    assert labor_total_cents(0, 500_000) == 0


def test_estimate_total_is_labor_plus_materials_in_whole_tyiyn():
    labor, materials, total = estimate_total_cents(
        90, 120_000, [(Decimal("2"), 1050), (Decimal("0.5"), 333)]
    )
    assert (labor, materials, total) == (180_000, 2100 + 167, 180_000 + 2100 + 167)
    assert all(isinstance(v, int) for v in (labor, materials, total))
