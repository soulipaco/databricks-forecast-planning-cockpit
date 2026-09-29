"""Validated inputs and normalized outputs for one series and one origin."""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class Observation:
    ds: date
    y: float


@dataclass(frozen=True)
class Prediction:
    ds: date
    lead_day: int
    prediction: float
    raw_prediction: float
    lower: float | None = None
    upper: float | None = None
    raw_lower: float | None = None
    raw_upper: float | None = None
    interval_level: float | None = None
    transformed: bool = False
    is_fallback: bool = False


@dataclass(frozen=True)
class ForecastResult:
    model_id: str
    series_id: str
    origin: date
    predictions: tuple[Prediction, ...]
    status: str = "success"
    wall_seconds: float | None = None
    lineage: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status != "success" or len(self.predictions) != 28:
            raise ValueError("A successful forecast requires exactly 28 predictions")
        if tuple(p.ds for p in self.predictions) != tuple(
            self.origin + timedelta(days=i) for i in range(1, 29)
        ):
            raise ValueError("Predictions must cover all 28 future calendar dates in order")
        if any(p.lead_day != i for i, p in enumerate(self.predictions, 1)):
            raise ValueError("Prediction lead_day must match the future calendar grid")


def _as_date(value: Any, name: str) -> date:
    if isinstance(value, datetime):
        if value.time() != datetime.min.time():
            raise ValueError(f"{name} must be a civil date")
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{name} must be an ISO civil date") from exc
    # pandas Timestamp is a datetime subclass; numpy datetime64 is deliberately
    # not accepted because its timezone/day semantics are otherwise ambiguous.
    raise TypeError(f"{name} must be a date or ISO date string")


def _records(history: Any) -> Iterable[Mapping[str, Any]]:
    if hasattr(history, "to_dict") and hasattr(history, "columns"):
        if not {"ds", "y"}.issubset(set(history.columns)):
            raise ValueError("history requires ds and y columns")
        return history[["ds", "y"]].to_dict("records")
    return history


def validate_inputs(
    history: Any, future_dates: Iterable[Any], *, origin: Any
) -> tuple[tuple[Observation, ...], tuple[date, ...], date]:
    """Reject leakage, gaps and malformed values before any model is invoked."""
    cutoff = _as_date(origin, "origin")
    rows: list[Observation] = []
    for record in _records(history):
        if not isinstance(record, Mapping) or "ds" not in record or "y" not in record:
            raise ValueError("history rows require ds and y")
        ds = _as_date(record["ds"], "history.ds")
        try:
            y = float(record["y"])
        except (TypeError, ValueError) as exc:
            raise ValueError("history.y must be finite and non-negative") from exc
        if not isfinite(y) or y < 0:
            raise ValueError("history.y must be finite and non-negative")
        rows.append(Observation(ds, y))
    if len(rows) < 7:
        raise ValueError("At least seven observed days are required")
    if rows[-1].ds != cutoff:
        raise ValueError("Last observed date must equal origin")
    if any(b.ds != a.ds + timedelta(days=1) for a, b in itertools.pairwise(rows)):
        raise ValueError("History must be a sorted, unique, gap-free daily series")
    if len(rows) > 1095:
        raise ValueError("History exceeds the 1,095-day training window")
    dates = tuple(_as_date(ds, "future_dates") for ds in future_dates)
    expected = tuple(cutoff + timedelta(days=i) for i in range(1, 29))
    if dates != expected:
        raise ValueError("future_dates must be exactly origin+1 through origin+28")
    return tuple(rows), dates, cutoff


def publish_prediction(
    ds: date,
    lead_day: int,
    raw_prediction: float,
    *,
    raw_lower: float | None = None,
    raw_upper: float | None = None,
    interval_level: float | None = None,
) -> Prediction:
    """Keep raw values and apply the protocol's shared non-negative policy."""
    values = (raw_prediction, raw_lower, raw_upper)
    if any(v is not None and (not isinstance(v, (int, float)) or not isfinite(v)) for v in values):
        raise ValueError("Forecast values must be finite")
    if (raw_lower is None) != (raw_upper is None):
        raise ValueError("Intervals require both bounds")
    if raw_lower is None and interval_level is not None:
        raise ValueError("Interval level requires bounds")
    if raw_lower is not None:
        if raw_lower > raw_upper:
            raise ValueError("Raw interval lower exceeds upper")
        if interval_level is None or not 0 < interval_level < 1:
            raise ValueError("Interval level must be between zero and one")
    prediction = max(0.0, float(raw_prediction))
    lower = None if raw_lower is None else max(0.0, float(raw_lower))
    upper = None if raw_upper is None else max(0.0, float(raw_upper))
    return Prediction(
        ds,
        lead_day,
        prediction,
        float(raw_prediction),
        lower,
        upper,
        None if raw_lower is None else float(raw_lower),
        None if raw_upper is None else float(raw_upper),
        interval_level,
        any(v is not None and v < 0 for v in values),
    )
