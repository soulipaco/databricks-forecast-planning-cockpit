"""Two-model, two-origin 2024 development evaluation over all selected series.

This is intentionally distinct from the three-model frozen 2025 benchmark.
No v2 forecast is inferred or substituted when the workspace capability is blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, date, datetime
from math import isfinite
from pathlib import Path
from typing import Any

from nyc311_forecast.contracts import assert_unique, validate_forecast
from nyc311_forecast.evaluation.metrics import score
from nyc311_forecast.evaluation.splits import DEVELOPMENT_ORIGINS, bounded_history, future_dates
from nyc311_forecast.models import prophet_adapter, snaive
from nyc311_forecast.models.prophet_adapter import ProphetParameters

ROOT = Path(__file__).resolve().parents[2]
SELECTION_PATH = ROOT / "data/series_manifest/selection-v1.json"
SILVER_PATH = ROOT / "data/silver/development-silver-20260929/daily_requests.jsonl"
TUNING_DIR = ROOT / "evidence/development_tuning_full_20260929"
MODEL_IDS = ("snaive7", "prophet_tuned")
STATUS = "partial_two_model_development_not_benchmark"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs(
    selection_path: Path = SELECTION_PATH,
    silver_path: Path = SILVER_PATH,
    tuning_dir: Path = TUNING_DIR,
) -> tuple[tuple[str, ...], dict[str, list[dict]], dict[str, ProphetParameters], dict]:
    """Require complete 20-trial checkpoints and matching immutable inputs."""
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    series_ids = tuple(row["series_id"] for row in selection["candidates"] if row["selected"])
    if len(series_ids) != 21 or len(set(series_ids)) != 21:
        raise ValueError("Expected 21 unique selected series")
    silver_manifest = json.loads((silver_path.parent / "manifest.json").read_text(encoding="utf-8"))
    tuning_manifest = json.loads((tuning_dir / "manifest.json").read_text(encoding="utf-8"))
    selection_sha, silver_sha = _sha(selection_path), _sha(silver_path)
    if (
        silver_manifest.get("status") != "complete"
        or silver_manifest.get("series_manifest_hash") != selection_sha
        or silver_manifest.get("daily_payload_hash") != silver_sha
    ):
        raise ValueError("Silver snapshot does not reconcile with selection manifest")
    if (
        tuning_manifest.get("status") != "development_tuning"
        or tuning_manifest.get("n_trials") != 20
        or tuning_manifest.get("seed") != 42
        or tuning_manifest.get("series_ids") != list(series_ids)
        or tuning_manifest.get("selection_sha256") != selection_sha
        or tuning_manifest.get("silver_sha256") != silver_sha
        or tuning_manifest.get("silver_snapshot_id") != silver_manifest.get("snapshot_id")
        or tuning_manifest.get("inner_origins") != ["2024-01-31", "2024-05-31", "2024-09-30"]
    ):
        raise ValueError("Tuning manifest does not match registered full development run")
    parameters: dict[str, ProphetParameters] = {}
    checkpoint_hashes: dict[str, str] = {}
    for index, series_id in enumerate(series_ids):
        path = tuning_dir / f"series-{index:02d}.json"
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        trials = checkpoint.get("trials", [])
        if (
            checkpoint.get("status") != "complete"
            or checkpoint.get("series_id") != series_id
            or checkpoint.get("n_trials") != 20
            or checkpoint.get("seed") != 42
            or len(trials) != 20
            or not any(t.get("state") == "COMPLETE" for t in trials)
        ):
            raise ValueError(f"Incomplete or mismatched tuning checkpoint: {path}")
        if not isfinite(float(checkpoint["pooled_wape"])):
            raise ValueError(f"Invalid tuning objective: {series_id}")
        parameters[series_id] = ProphetParameters(**checkpoint["parameters"])
        checkpoint_hashes[series_id] = _sha(path)
    by_series: dict[str, list[dict]] = {series_id: [] for series_id in series_ids}
    with silver_path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["series_id"] not in by_series:
                continue
            ds = date.fromisoformat(row["ds"])
            if ds.year >= 2025:
                raise ValueError("Development comparison input contains 2025 data")
            by_series[row["series_id"]].append({"ds": ds, "y": row["y"]})
    provenance = {
        "selection_sha256": selection_sha,
        "selection_manifest_sha256": selection_sha,
        "silver_sha256": silver_sha,
        "silver_snapshot_id": silver_manifest["snapshot_id"],
        "tuning_manifest_sha256": _sha(tuning_dir / "manifest.json"),
        "tuning_code_sha": tuning_manifest["code_sha"],
        "tuning_checkpoint_sha256_by_series": checkpoint_hashes,
        "prophet_n_trials_per_series": 20,
        "prophet_seed": 42,
    }
    return series_ids, by_series, parameters, provenance


def run_comparison(
    series_ids: tuple[str, ...],
    by_series: Mapping[str, list[dict]],
    prophet_parameters: Mapping[str, ProphetParameters],
    *,
    adapters: Mapping[str, Any] | None = None,
) -> dict:
    """Preserve all expected attempts and score only complete 28-day outputs."""
    if not series_ids or len(set(series_ids)) != len(series_ids):
        raise ValueError("series_ids must be nonempty and unique")
    if set(prophet_parameters) != set(series_ids):
        raise ValueError("Every series requires its own frozen Prophet parameters")
    adapters = adapters or {"snaive7": snaive, "prophet_tuned": prophet_adapter}
    if set(adapters) != set(MODEL_IDS):
        raise ValueError("Only snaive7 and prophet_tuned are allowed")
    attempts, values, cells = [], [], []
    for origin in DEVELOPMENT_ORIGINS:
        dates = future_dates(origin)
        for series_id in series_ids:
            rows = by_series.get(series_id, [])
            for model_id in MODEL_IDS:
                key = {"origin": origin.isoformat(), "series_id": series_id, "model_id": model_id}
                attempt = {**key, "attempt_no": 1, "status": "failed"}
                cell = {
                    **key,
                    "horizon_days": 28,
                    "n_expected": 28,
                    "n_actual": 0,
                    "n_predictions": 0,
                    "status": "failed",
                }
                try:
                    history = bounded_history(rows, origin)
                    actual_rows = [row for row in rows if row["ds"] in dates]
                    cell["n_actual"] = len(actual_rows)
                    if len(actual_rows) != 28 or len({row["ds"] for row in actual_rows}) != 28:
                        raise ValueError("Actual validation grid has missing or duplicate dates")
                    actual_by_date = {row["ds"]: row["y"] for row in actual_rows}
                    actual = [actual_by_date[ds] for ds in dates]
                    cell["n_actual"] = len(actual)
                    config = prophet_parameters[series_id] if model_id == "prophet_tuned" else None
                    result = adapters[model_id].forecast(
                        history,
                        dates,
                        series_id=series_id,
                        origin=origin,
                        model_config=config,
                        execution_context=None,
                    )
                    if (
                        result.model_id != model_id
                        or result.series_id != series_id
                        or result.origin != origin
                    ):
                        raise ValueError("Adapter returned the wrong forecast identity")
                    cell["n_predictions"] = len(result.predictions)
                    normalized = validate_forecast(
                        (
                            {
                                "ds": p.ds,
                                "prediction": p.prediction,
                                "lower": p.lower,
                                "upper": p.upper,
                            }
                            for p in result.predictions
                        ),
                        origin,
                    )
                    cell["n_predictions"] = len(normalized)
                    if tuple(p.ds for p in result.predictions) != tuple(dates):
                        raise ValueError("Forecast dates are not in lead order")
                    if any(p.lead_day != lead for lead, p in enumerate(result.predictions, 1)):
                        raise ValueError("Forecast lead days are invalid")
                    if any(p.is_fallback for p in result.predictions):
                        raise ValueError("Fallback rows cannot enter development scoring")
                    lower = [p.lower for p in result.predictions]
                    upper = [p.upper for p in result.predictions]
                    if model_id == "snaive7" and any(
                        lo is not None or hi is not None for lo, hi in zip(lower, upper)
                    ):
                        raise ValueError("Baseline must not emit an interval")
                    if model_id == "prophet_tuned" and any(
                        lo is None or hi is None for lo, hi in zip(lower, upper)
                    ):
                        raise ValueError("Prophet interval grid is incomplete")
                    metrics = score(
                        actual,
                        [p.prediction for p in result.predictions],
                        [row["y"] for row in history],
                        None if model_id == "snaive7" else lower,
                        None if model_id == "snaive7" else upper,
                    )
                    cell.update(status="complete", metrics=asdict(metrics))
                    values.extend(
                        {
                            **key,
                            "ds": p.ds.isoformat(),
                            "lead_day": p.lead_day,
                            "actual": actual_by_date[p.ds],
                            "prediction": p.prediction,
                            "raw_prediction": p.raw_prediction,
                            "lower": p.lower,
                            "upper": p.upper,
                            "raw_lower": p.raw_lower,
                            "raw_upper": p.raw_upper,
                            "interval_level": p.interval_level,
                            "transformed": p.transformed,
                            "is_fallback": p.is_fallback,
                        }
                        for p in result.predictions
                    )
                    attempt.update(status="success", wall_seconds=result.wall_seconds)
                except Exception as exc:  # noqa: BLE001 - preserve every model-cell failure
                    attempt.update(
                        error_class=type(exc).__name__, safe_error_message=str(exc)[:240]
                    )
                    cell["error_class"] = type(exc).__name__
                attempts.append(attempt)
                cells.append(cell)
    expected = len(series_ids) * len(DEVELOPMENT_ORIGINS) * len(MODEL_IDS)
    if len(attempts) != expected or len(cells) != expected:
        raise AssertionError("Expected model/series/origin grid was lost")
    assert_unique("forecast_values", ({"run_id": "development", **row} for row in values))
    successful = {
        (r["origin"], r["series_id"], r["model_id"]) for r in cells if r["status"] == "complete"
    }
    paired = sum(
        all((origin.isoformat(), series_id, model_id) in successful for model_id in MODEL_IDS)
        for origin in DEVELOPMENT_ORIGINS
        for series_id in series_ids
    )
    return {
        "status": STATUS,
        "model_ids": list(MODEL_IDS),
        "origins": [origin.isoformat() for origin in DEVELOPMENT_ORIGINS],
        "series_ids": list(series_ids),
        "expected_cells": expected,
        "complete_cells": len(successful),
        "failed_cells": expected - len(successful),
        "paired_two_model_cells": paired,
        "attempts": attempts,
        "evaluation_cells": cells,
        "forecast_values": values,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output already exists; choose a new evidence path")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        raise RuntimeError("Commit code, data and tuning checkpoints before a traceable run")
    code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    series_ids, by_series, parameters, provenance = load_inputs()
    output = run_comparison(series_ids, by_series, parameters)
    output.update(provenance)
    output.update(
        {
            "run_id": f"development-two-model-{code_sha[:12]}",
            "code_sha": code_sha,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "prophet_parameters_by_series": {
                series_id: asdict(parameters[series_id]) for series_id in series_ids
            },
            "native_v2_status": "unavailable_runtime_dependency_installation",
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(output, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                "run_id": output["run_id"],
                "status": STATUS,
                "expected_cells": output["expected_cells"],
                "complete_cells": output["complete_cells"],
                "paired_two_model_cells": output["paired_two_model_cells"],
                "forecast_values": len(output["forecast_values"]),
                "output": str(args.output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
