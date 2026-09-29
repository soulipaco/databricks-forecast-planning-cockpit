"""Validate and stage the full, partial two-model 2024 development run."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from nyc311_forecast.platform.persist_smoke import FIELDS, UPSTREAM_SHA

STATUS = "partial_two_model_development_not_benchmark"
MODELS = ("snaive7", "prophet_tuned")
ORIGINS = ("2024-10-31", "2024-11-30")
RUN_ID = re.compile(r"development-two-model-[0-9a-f]{12}\Z")


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _finite(value, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} is not numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} is not finite")
    return number


def transform(source: dict) -> tuple[dict[str, list[dict]], dict]:
    if source.get("status") != STATUS or not RUN_ID.fullmatch(source.get("run_id", "")):
        raise ValueError("Only a labeled full two-model development run is allowed")
    if source.get("model_ids") != list(MODELS) or source.get("origins") != list(ORIGINS):
        raise ValueError("Unexpected model/origin grid")
    series = source.get("series_ids", [])
    if len(series) != 21 or len(set(series)) != 21:
        raise ValueError("Expected 21 unique selected series")
    if set(source.get("prophet_parameters_by_series", {})) != set(series):
        raise ValueError("Missing per-series Prophet parameters")
    expected_keys = {(origin, series_id, model_id) for origin in ORIGINS
                     for series_id in series for model_id in MODELS}
    if source.get("expected_cells") != 84 or len(source.get("attempts", [])) != 84 or len(source.get("evaluation_cells", [])) != 84:
        raise ValueError("Expected 84 attempts and evaluation cells")
    if not re.fullmatch(r"[0-9a-f]{40}", source.get("code_sha", "")) or source["run_id"] != f"development-two-model-{source['code_sha'][:12]}":
        raise ValueError("Run ID/code SHA mismatch")
    required_lineage = ("silver_snapshot_id", "silver_sha256", "selection_sha256",
                        "tuning_manifest_sha256", "tuning_checkpoint_sha256_by_series")
    if any(not source.get(name) for name in required_lineage):
        raise ValueError("Development lineage incomplete")
    if set(source["tuning_checkpoint_sha256_by_series"]) != set(series):
        raise ValueError("Tuning checkpoints do not cover selected series")
    config = {key: source[key] for key in ("model_ids", "origins", "series_ids",
              "prophet_parameters_by_series", "tuning_manifest_sha256",
              "tuning_checkpoint_sha256_by_series")}
    config_hash = _hash(json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())
    run_id = source["run_id"]
    run = dict(zip(FIELDS["forecast_runs"], (
        run_id, "nyc311-development-two-model", source["silver_snapshot_id"],
        None, config_hash, source["code_sha"], UPSTREAM_SHA, "local_2024_development",
        None, source["generated_at_utc"], STATUS, None)))
    attempts, values, cells = [], [], []
    attempt_keys = set()
    cell_keys = set()
    successful = set()
    for item in source["attempts"]:
        key = (item["origin"], item["series_id"], item["model_id"])
        if key not in expected_keys or key in attempt_keys or item.get("attempt_no") != 1:
            raise ValueError("Attempt grid has a missing, duplicate or unexpected key")
        attempt_keys.add(key)
        state = item.get("status")
        if state not in {"success", "failed"}:
            raise ValueError("Attempt status invalid")
        if state == "failed" and not item.get("error_class"):
            raise ValueError("Failed attempt lacks an error class")
        attempts.append({"run_id": run_id, "model_id": key[2], "origin": key[0],
                         "series_id": key[1], "attempt_no": 1, "status": state,
                         "error_class": item.get("error_class"),
                         "safe_error_message": item.get("safe_error_message"),
                         "query_id": None, "queue_seconds": None, "compute_seconds": None,
                         "wall_seconds": item.get("wall_seconds"), "retry_reason": None})
    for item in source["evaluation_cells"]:
        key = (item["origin"], item["series_id"], item["model_id"])
        if key not in expected_keys or key in cell_keys:
            raise ValueError("Evaluation grid has a missing, duplicate or unexpected key")
        cell_keys.add(key)
        state = item.get("status")
        if state not in {"complete", "failed"} or item.get("horizon_days") != 28 or item.get("n_expected") != 28:
            raise ValueError("Evaluation status/horizon invalid")
        if not 0 <= item.get("n_actual", -1) <= 28 or not 0 <= item.get("n_predictions", -1) <= 28:
            raise ValueError("Invalid evaluation coverage")
        metric = item.get("metrics") if state == "complete" else None
        if state == "complete":
            if not metric or item["n_actual"] != 28 or item["n_predictions"] != 28 or metric.get("n") != 28:
                raise ValueError("Complete cell lacks a full scored horizon")
            successful.add(key)
        elif item.get("metrics") is not None:
            raise ValueError("Failed cell carries metrics")
        cells.append({"run_id": run_id, "model_id": key[2], "origin": key[0],
                      "series_id": key[1], "horizon_days": 28, "n_expected": 28,
                      "n_actual": item["n_actual"], "n_predictions": item["n_predictions"],
                      "paired_status": "complete_two_model_development" if state == "complete" else "failed_two_model_development",
                      "abs_error_sum": _finite(metric["abs_error_sum"], "abs_error_sum") if metric else None,
                      "actual_sum": _finite(metric["actual_sum"], "actual_sum") if metric else None,
                      "signed_error_sum": _finite(metric["signed_error_sum"], "signed_error_sum") if metric else None,
                      "mase_denominator": _finite(metric["mase_denominator"], "mase_denominator") if metric else None,
                      "interval_n": metric["interval_n"] if metric else None,
                      "interval_hits": metric["interval_hits"] if metric else None,
                      "interval_width_sum": _finite(metric["interval_width_sum"], "interval_width_sum") if metric else None,
                      "interval_score_sum": _finite(metric["interval_score_sum"], "interval_score_sum") if metric else None})
    if attempt_keys != expected_keys or cell_keys != expected_keys:
        raise ValueError("Incomplete development grid")
    success_attempts = {(row["origin"], row["series_id"], row["model_id"])
                        for row in attempts if row["status"] == "success"}
    if success_attempts != successful:
        raise ValueError("Attempt and evaluation success sets disagree")
    forecast_keys = set()
    by_cell = Counter()
    for item in source.get("forecast_values", []):
        key = (item["origin"], item["series_id"], item["model_id"])
        if key not in successful or item.get("lead_day") not in range(1, 29):
            raise ValueError("Forecast row does not belong to a complete cell")
        if date.fromisoformat(item["ds"]) != date.fromisoformat(item["origin"]) + timedelta(days=item["lead_day"]):
            raise ValueError("Forecast date/lead mismatch")
        value_key = (*key, item["ds"])
        if value_key in forecast_keys or item.get("is_fallback"):
            raise ValueError("Duplicate or fallback forecast row")
        forecast_keys.add(value_key)
        by_cell[key] += 1
        for name in ("prediction", "raw_prediction"):
            _finite(item[name], name)
        if (item["lower"] is None) != (item["upper"] is None):
            raise ValueError("Partial interval")
        values.append({"run_id": run_id, "model_id": key[2], "origin": key[0],
                       "series_id": key[1], "ds": item["ds"], "lead_day": item["lead_day"],
                       "prediction": item["prediction"], "lower": item["lower"], "upper": item["upper"],
                       "interval_level": item["interval_level"], "raw_prediction": item["raw_prediction"],
                       "raw_lower": item["raw_lower"], "raw_upper": item["raw_upper"],
                       "transformed": item["transformed"], "is_fallback": False})
    if set(by_cell) != successful or any(by_cell[key] != 28 for key in successful):
        raise ValueError("Successful forecast cells do not each have 28 rows")
    if source.get("complete_cells") != len(successful) or source.get("failed_cells") != 84 - len(successful):
        raise ValueError("Reported completion counts disagree")
    paired = sum(all((origin, series_id, model) in successful for model in MODELS)
                 for origin in ORIGINS for series_id in series)
    if source.get("paired_two_model_cells") != paired:
        raise ValueError("Reported pairing disagrees")
    rows = {"forecast_runs": [run], "forecast_attempts": attempts,
            "forecast_values": values, "evaluation_cells": cells}
    summary = {"expected_cells": 84, "complete_cells": len(successful),
               "failed_cells": 84 - len(successful), "paired_two_model_cells": paired}
    return rows, summary


def stage(source_path: Path, output_dir: Path) -> dict:
    source_bytes = source_path.read_bytes()
    rows, summary = transform(json.loads(source_bytes))
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"stage_id": output_dir.name, "run_id": rows["forecast_runs"][0]["run_id"],
                "status": STATUS, "source_sha256": _hash(source_bytes), **summary, "tables": {}}
    for table, table_rows in rows.items():
        payload = "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in table_rows).encode()
        path = output_dir / f"{table}.jsonl"
        if path.exists() and path.read_bytes() != payload:
            raise ValueError(f"Existing stage differs: {path}")
        path.write_bytes(payload)
        manifest["tables"][table] = {"rows": len(table_rows), "sha256": _hash(payload)}
    content = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    path = output_dir / "manifest.json"
    if path.exists() and path.read_bytes() != content:
        raise ValueError("Existing stage manifest differs")
    path.write_bytes(content)
    return manifest
