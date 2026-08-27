"""Cart model and discount arithmetic.

All amounts are integer cents to avoid float money.
"""


class Cart:
    def __init__(self, lines: list[dict] | None = None):
        self.lines = list(lines or [])

    def total_cents(self) -> int:
        return sum(int(line["unit_cents"]) * int(line["qty"]) for line in self.lines)


def apply_discount(total_cents: int, percent: int) -> int:
    """Apply a percentage discount to an amount in cents."""
    discounted = total_cents * percent / 100
    return round(total_cents - discounted)
