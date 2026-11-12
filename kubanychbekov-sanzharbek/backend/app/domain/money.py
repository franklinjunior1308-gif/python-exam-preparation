"""Money helpers. Amounts are whole tyiyn (1 KGS = 100 tyiyn), never binary floats (DATA-04).

Rounding is always half-up on exact decimals, so the same input gives the same total everywhere.
"""

from decimal import ROUND_HALF_UP, Decimal

CURRENCY = "KGS"


def line_total_cents(quantity: Decimal, unit_price_cents: int) -> int:
    """quantity x unit price, rounded half-up to a whole tyiyn."""
    return int((quantity * unit_price_cents).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def labor_total_cents(labor_minutes: int, rate_per_hour_cents: int) -> int:
    """Minutes at an hourly rate, rounded half-up to a whole tyiyn."""
    exact = Decimal(labor_minutes) * Decimal(rate_per_hour_cents) / Decimal(60)
    return int(exact.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def estimate_total_cents(
    labor_minutes: int, rate_per_hour_cents: int, lines: list[tuple[Decimal, int]]
) -> tuple[int, int, int]:
    """Return (labor, materials, total) in tyiyn."""
    labor = labor_total_cents(labor_minutes, rate_per_hour_cents)
    materials = sum(line_total_cents(q, price) for q, price in lines)
    return labor, materials, labor + materials
