"""Bounded two-origin development integration slice; never a benchmark result."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from nyc311_forecast.evaluation.metrics import score
from nyc311_forecast.evaluation.splits import DEVELOPMENT_ORIGINS, bounded_history, future_dates
from nyc311_forecast.models import prophet_adapter, snaive
from nyc311_forecast.models.prophet_adapter import ProphetParameters

ROOT = Path(__file__).resolve().parents[2]
SILVER_DIR = ROOT / "data/silver/development-silver-20260929"
SELECTION_PATH = ROOT / "data/series_manifest/selection-v1.json"
PARAMETERS = ProphetParameters(0.05, 1.0, "additive")
MODELS = ("snaive7", "prophet_fixed_smoke")


def load_selected_series(
    limit: int,
) -> tuple[tuple[str, ...], dict[str, list[dict[str, Any]]], dict]:
    if not 1 <= limit <= 3:
        raise ValueError("Development integration slice allows one to three series")
    selection = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    selected = tuple(row["series_id"] for row in selection["candidates"] if row["selected"])
    if len(selected) < limit:
        raise ValueError("Series manifest has fewer selected series than requested")
    chosen = selected[:limit]
    manifest = json.loads((SILVER_DIR / "manifest.json").read_text(encoding="utf-8"))
    selection_hash = hashlib.sha256(SELECTION_PATH.read_bytes()).hexdigest()
    if manifest["status"] != "complete" or manifest["series_manifest_hash"] != selection_hash:
        raise ValueError("Silver and selection manifests do not match")
    by_series: dict[str, list[dict[str, Any]]] = {series_id: [] for series_id in chosen}
    with (SILVER_DIR / "daily_requests.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["series_id"] in by_series:
                by_series[row["series_id"]].append(
                    {"ds": date.fromisoformat(row["ds"]), "y": row["y"]}
                )
    return chosen, by_series, manifest


def run_slice(
    series_ids: tuple[str, ...],
    by_series: Mapping[str, list[dict[str, Any]]],
    adapters: Mapping[str, Any],
) -> dict:
    """Predeclare the grid and retain each success or failure without retries."""
    if set(adapters) != set(MODELS):
        raise ValueError("Development slice requires both named local models")
    attempts: list[dict] = []
    values: list[dict] = []
    cells: list[dict] = []
    for origin in DEVELOPMENT_ORIGINS:
        dates = future_dates(origin)
        for series_id in series_ids:
            rows = by_series[series_id]
            for model_id in MODELS:
                attempt = {
                    "origin": origin.isoformat(),
                    "series_id": series_id,
                    "model_id": model_id,
                    "attempt_no": 1,
                    "status": "failed",
                }
                try:
                    history = bounded_history(rows, origin)
                    actual_by_date = {row["ds"]: row["y"] for row in rows}
                    actual = [actual_by_date[day] for day in dates]
                    adapter, config = adapters[model_id]
                    result = adapter.forecast(
                        history,
                        dates,
                        series_id=series_id,
                        origin=origin,
                        model_config=config,
                        execution_context=None,
                    )
                    if result.model_id != (
                        "prophet_tuned" if model_id == "prophet_fixed_smoke" else model_id
                    ):
                        raise ValueError("Adapter returned a different model ID")
                    prediction = [value.prediction for value in result.predictions]
                    lower = [value.lower for value in result.predictions]
                    upper = [value.upper for value in result.predictions]
                    if any((lo is None) != (hi is None) for lo, hi in zip(lower, upper)):
                        raise ValueError("Partial interval bounds")
                    if any(lo is None for lo in lower) != all(lo is None for lo in lower):
                        raise ValueError("Incomplete interval grid")
                    metrics = score(
                        actual,
                        prediction,
                        [row["y"] for row in history],
                        None if all(lo is None for lo in lower) else lower,
                        None if all(hi is None for hi in upper) else upper,
                    )
                    cell_values = [
                        {
                            "origin": origin.isoformat(),
                            "series_id": series_id,
                            "model_id": model_id,
                            "ds": value.ds.isoformat(),
                            "lead_day": value.lead_day,
                            "actual": actual_by_date[value.ds],
                            "prediction": value.prediction,
                            "raw_prediction": value.raw_prediction,
                            "lower": value.lower,
                            "upper": value.upper,
                            "raw_lower": value.raw_lower,
                            "raw_upper": value.raw_upper,
                            "transformed": value.transformed,
                        }
                        for value in result.predictions
                    ]
                    if len(cell_values) != 28:
                        raise ValueError("Incomplete forecast output")
                    values.extend(cell_values)
                    cells.append(
                        {
                            "origin": origin.isoformat(),
                            "series_id": series_id,
                            "model_id": model_id,
                            "metrics": asdict(metrics),
                        }
                    )
                    attempt.update(status="success", wall_seconds=result.wall_seconds)
                except (KeyError, TypeError, ValueError, RuntimeError) as exc:
                    attempt.update(
                        error_class=type(exc).__name__, safe_error_message=str(exc)[:240]
                    )
                attempts.append(attempt)
    expected_cells = len(series_ids) * len(DEVELOPMENT_ORIGINS) * len(MODELS)
    if len(attempts) != expected_cells:
        raise AssertionError("Expected attempt grid was not preserved")
    successful = {(row["origin"], row["series_id"], row["model_id"]) for row in cells}
    paired = sum(
        all((origin.isoformat(), series_id, model_id) in successful for model_id in MODELS)
        for origin in DEVELOPMENT_ORIGINS
        for series_id in series_ids
    )
    return {
        "status": "smoke_only_not_benchmark",
        "origins": [origin.isoformat() for origin in DEVELOPMENT_ORIGINS],
        "series_ids": list(series_ids),
        "expected_cells": expected_cells,
        "complete_cells": len(cells),
        "paired_local_cells": paired,
        "attempts": attempts,
        "evaluation_cells": cells,
        "forecast_values": values,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--series-limit", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output already exists; choose a new evidence path")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        raise RuntimeError("Commit code and data before a traceable development run")
    git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    series_ids, by_series, silver_manifest = load_selected_series(args.series_limit)
    output = run_slice(
        series_ids,
        by_series,
        {
            "snaive7": (snaive, None),
            "prophet_fixed_smoke": (prophet_adapter, PARAMETERS),
        },
    )
    output.update(
        {
            "run_id": f"development-slice-{git_sha[:12]}",
            "code_sha": git_sha,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "silver_snapshot_id": silver_manifest["snapshot_id"],
            "silver_payload_sha256": silver_manifest["daily_payload_hash"],
            "selection_manifest_sha256": silver_manifest["series_manifest_hash"],
            "prophet_parameter_source": "fixed_smoke_values_not_tuned",
            "prophet_parameters": asdict(PARAMETERS),
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "run_id": output["run_id"],
                "status": output["status"],
                "expected_cells": output["expected_cells"],
                "complete_cells": output["complete_cells"],
                "paired_local_cells": output["paired_local_cells"],
                "forecast_values": len(output["forecast_values"]),
                "output": str(args.output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
