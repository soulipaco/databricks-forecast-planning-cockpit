"""Recompute every 2024 development score cell from stored prediction rows."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def verify(source: dict) -> dict:
    if source.get("status") != "partial_two_model_development_not_benchmark":
        raise ValueError("Expected two-model 2024 development output")
    if source.get("expected_cells") != 84 or source.get("complete_cells") != 84:
        raise ValueError("Full development grid is required")
    grouped = defaultdict(list)
    for row in source["forecast_values"]:
        grouped[(row["origin"], row["series_id"], row["model_id"])].append(row)
    if len(grouped) != 84 or sum(map(len, grouped.values())) != 2352:
        raise ValueError("Prediction population differs from expected grid")
    seen = set()
    for cell in source["evaluation_cells"]:
        key = (cell["origin"], cell["series_id"], cell["model_id"])
        if key in seen or cell["status"] != "complete":
            raise ValueError("Duplicate or incomplete score cell")
        seen.add(key)
        rows = grouped[key]
        if len(rows) != 28 or sorted(row["lead_day"] for row in rows) != list(range(1, 29)):
            raise ValueError(f"Incomplete prediction dates for {key}")
        metric = cell["metrics"]
        abs_sum = sum(abs(row["prediction"] - row["actual"]) for row in rows)
        actual_sum = sum(row["actual"] for row in rows)
        signed_sum = sum(row["prediction"] - row["actual"] for row in rows)
        interval = [row for row in rows if row["lower"] is not None and row["upper"] is not None]
        if interval and len(interval) != 28:
            raise ValueError(f"Partial interval for {key}")
        hits = sum(row["lower"] <= row["actual"] <= row["upper"] for row in interval)
        width = sum(row["upper"] - row["lower"] for row in interval)
        interval_score = sum(
            row["upper"]
            - row["lower"]
            + (
                10 * (row["lower"] - row["actual"])
                if row["actual"] < row["lower"]
                else 10 * (row["actual"] - row["upper"])
                if row["actual"] > row["upper"]
                else 0
            )
            for row in interval
        )
        observed = {
            "abs_error_sum": abs_sum,
            "actual_sum": actual_sum,
            "signed_error_sum": signed_sum,
            "interval_width_sum": width,
            "interval_score_sum": interval_score,
        }
        for name, value in observed.items():
            if not math.isclose(value, metric[name], rel_tol=1e-10, abs_tol=1e-6):
                raise ValueError(f"{name} differs for {key}")
        if (metric["interval_n"], metric["interval_hits"]) != (len(interval), hits):
            raise ValueError(f"Interval counts differ for {key}")
    if seen != set(grouped):
        raise ValueError("Prediction and evaluation populations differ")
    return {
        "status": "verified_two_model_development_prediction_arithmetic",
        "run_id": source["run_id"],
        "verified_cells": len(seen),
        "verified_predictions": sum(len(rows) for rows in grouped.values()),
        "measures": [
            "abs_error_sum",
            "actual_sum",
            "signed_error_sum",
            "interval_n",
            "interval_hits",
            "interval_width_sum",
            "interval_score_sum",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Evidence output already exists")
    result = verify(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
