"""Reporting helpers."""


def summarize(rows: list[dict]) -> tuple[int, float]:
    """Return (count, total) over the numeric ``value`` field of each row."""
    values = [row["value"] for row in rows]
    return len(values), sum(values)
