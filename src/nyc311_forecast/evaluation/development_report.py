"""Paired, two-model 2024 diagnostics; never a three-model benchmark."""

from __future__ import annotations

from collections import defaultdict
from math import isfinite
from statistics import median

STATUS = "partial_two_model_development_not_benchmark"
MODELS = ("snaive7", "prophet_tuned")


def summarize(source: dict) -> dict:
    if source.get("status") != STATUS or source.get("model_ids") != list(MODELS):
        raise ValueError("Expected the labeled two-model development run")
    if source.get("expected_cells") != 84 or len(source.get("evaluation_cells", [])) != 84:
        raise ValueError("Incomplete expected development grid")
    cells = source["evaluation_cells"]
    keys = [(row["origin"], row["series_id"], row["model_id"]) for row in cells]
    expected = {
        (origin, series_id, model)
        for origin in source["origins"]
        for series_id in source["series_ids"]
        for model in MODELS
    }
    if len(expected) != 84 or set(keys) != expected or len(keys) != len(set(keys)):
        raise ValueError("Development cell grid differs from the registered population")
    successful = {
        (row["origin"], row["series_id"], row["model_id"]): row
        for row in cells
        if row["status"] == "complete"
        and row["n_actual"] == 28
        and row["n_predictions"] == 28
        and row.get("metrics", {}).get("n") == 28
    }
    if len(successful) != source.get("complete_cells"):
        raise ValueError("Reported complete cell count differs")
    if any(
        not isfinite(float(row["metrics"][field])) or float(row["metrics"][field]) < 0
        for row in successful.values()
        for field in ("abs_error_sum", "actual_sum")
    ):
        raise ValueError("Non-finite or negative score component")
    paired = [
        (origin, series_id)
        for origin in source["origins"]
        for series_id in source["series_ids"]
        if all((origin, series_id, model) in successful for model in MODELS)
    ]
    if len(paired) != source.get("paired_two_model_cells"):
        raise ValueError("Reported paired cell count differs")
    totals = {}
    for model in MODELS:
        selected = [
            successful[(origin, series_id, model)]["metrics"] for origin, series_id in paired
        ]
        actual_sum = sum(item["actual_sum"] for item in selected)
        abs_error_sum = sum(item["abs_error_sum"] for item in selected)
        by_series: dict[str, list[dict]] = defaultdict(list)
        for origin, series_id in paired:
            by_series[series_id].append(successful[(origin, series_id, model)]["metrics"])
        series_wape = [
            sum(item["abs_error_sum"] for item in values)
            / sum(item["actual_sum"] for item in values)
            for values in by_series.values()
            if sum(item["actual_sum"] for item in values) > 0
        ]
        totals[model] = {
            "paired_abs_error_sum": abs_error_sum,
            "paired_actual_sum": actual_sum,
            "paired_pooled_wape": abs_error_sum / actual_sum if actual_sum else None,
            "paired_series_median_wape": median(series_wape) if series_wape else None,
            "paired_series_with_defined_wape": len(series_wape),
        }
    return {
        "status": "two_model_2024_development_diagnostic_only",
        "run_id": source["run_id"],
        "expected_series_origin_pairs": 42,
        "paired_series_origin_pairs": len(paired),
        "expected_model_cells": 84,
        "complete_model_cells": len(successful),
        "failed_model_cells": 84 - len(successful),
        "models": totals,
        "limitation": "2024 development only; no ai_forecast v2 result or 2025 evaluation",
    }
