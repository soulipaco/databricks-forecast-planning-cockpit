"""Construct expected cells before comparing models; preserve failures."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date

from nyc311_forecast.contracts import validate_forecast


def coverage_report(
    series_ids: Iterable[str],
    origins: Iterable[date],
    models: Iterable[str],
    forecasts: Iterable[Mapping[str, object]],
) -> dict:
    series_ids = tuple(series_ids)
    origins = tuple(origins)
    models = tuple(models)
    expected = {(model, origin, series) for model in models for origin in origins for series in series_ids}
    if not expected:
        raise ValueError("Expected grid is empty")
    grouped: dict[tuple, list[Mapping[str, object]]] = defaultdict(list)
    for row in forecasts:
        key = (row["model_id"], row["origin"], row["series_id"])
        if key not in expected:
            raise ValueError(f"Unexpected forecast cell: {key}")
        if row.get("is_fallback"):
            continue
        grouped[key].append(row)
    complete: set[tuple] = set()
    invalid: dict[tuple, str] = {}
    for key in sorted(expected):
        try:
            validate_forecast(grouped[key], key[1])
        except (KeyError, ValueError) as exc:
            invalid[key] = str(exc)
        else:
            complete.add(key)
    model_names = {cell[0] for cell in expected}
    pairs = {(origin, series) for _, origin, series in expected}
    paired = {pair for pair in pairs if all((model, *pair) in complete for model in model_names)}
    per_model = {
        model: {
            "expected": sum(key[0] == model for key in expected),
            "complete": sum(key[0] == model for key in complete),
        }
        for model in sorted(model_names)
    }
    return {
        "per_model": per_model,
        "paired_cells": len(paired),
        "expected_pairs": len(pairs),
        "unrestricted_comparison": all(
            item["complete"] / item["expected"] >= 0.95 for item in per_model.values()
        ),
        "invalid": invalid,
    }
