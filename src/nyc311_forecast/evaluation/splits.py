"""Calendar split rules from protocol v1."""

from collections.abc import Mapping, Sequence
from datetime import date, timedelta

TUNING_ORIGINS = (date(2024, 1, 31), date(2024, 5, 31), date(2024, 9, 30))
DEVELOPMENT_ORIGINS = (date(2024, 10, 31), date(2024, 11, 30))
FINAL_ORIGINS = (date(2024, 12, 31),) + tuple(
    date(2025, m + 1, 1) - timedelta(days=1) for m in range(1, 12)
)


def bounded_history(rows: Sequence[Mapping], origin: date) -> list[Mapping]:
    """Return exactly the last 1,095 daily observations through origin."""
    first = origin - timedelta(days=1094)
    selected = sorted((r for r in rows if first <= r["ds"] <= origin), key=lambda r: r["ds"])
    expected = [first + timedelta(days=i) for i in range(1095)]
    if [r["ds"] for r in selected] != expected:
        raise ValueError("Training history has missing or duplicate dates")
    if any(r.get("y") is None for r in selected):
        raise ValueError("Training history contains unresolved targets")
    return selected


def future_dates(origin: date) -> list[date]:
    return [origin + timedelta(days=i) for i in range(1, 29)]
