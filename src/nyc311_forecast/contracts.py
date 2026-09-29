"""Contract v1 keys and finite forecast validation."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from datetime import date, timedelta

KEYS: dict[str, tuple[str, ...]] = {
    "source_partitions": ("snapshot_id", "partition_id"),
    "daily_requests": ("snapshot_id", "series_id", "ds"),
    "series_manifest": ("experiment_id", "series_id"),
    "forecast_runs": ("run_id",),
    "forecast_attempts": ("run_id", "model_id", "origin", "series_id", "attempt_no"),
    "forecast_values": ("run_id", "model_id", "origin", "series_id", "ds"),
    "evaluation_cells": ("run_id", "model_id", "origin", "series_id", "horizon_days"),
    "champion_policy": ("policy_id", "series_id"),
    "capacity_assumptions": ("scenario_id", "series_id", "ds"),
    "release_claims": ("release_id", "claim_id"),
}


def assert_unique(table: str, rows: Iterable[Mapping[str, object]]) -> None:
    fields = KEYS[table]
    seen: set[tuple[object, ...]] = set()
    for row in rows:
        key = tuple(row[field] for field in fields)
        if any(value is None for value in key):
            raise ValueError(f"Null key in {table}: {key}")
        if key in seen:
            raise ValueError(f"Duplicate key in {table}: {key}")
        seen.add(key)


def validate_forecast(rows: Iterable[Mapping[str, object]], origin: date) -> list[dict]:
    values = [dict(row) for row in rows]
    if len(values) != 28:
        raise ValueError("Forecast must contain exactly 28 rows")
    expected = {origin + timedelta(days=lead) for lead in range(1, 29)}
    actual = {row["ds"] for row in values}
    if actual != expected:
        raise ValueError("Forecast date grid is incomplete or contains unexpected dates")
    if len(actual) != len(values):
        raise ValueError("Duplicate forecast date")
    for row in values:
        for field in ("prediction", "lower", "upper"):
            value = row.get(field)
            if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError(f"Invalid {field} forecast value")
        if row["prediction"] is None:
            raise ValueError("Missing prediction")
        if (row.get("lower") is None) != (row.get("upper") is None):
            raise ValueError("Only one interval bound present")
        if row.get("lower") is not None and row["lower"] > row["upper"]:
            raise ValueError("Interval lower exceeds upper")
    return values
