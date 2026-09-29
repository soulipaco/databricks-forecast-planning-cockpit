"""Validate and stage one immutable local development smoke run."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

STATUS = "smoke_only_not_benchmark"
MODELS = {"snaive7", "prophet_fixed_smoke"}
UPSTREAM_SHA = "b2538be9d19abb191a2c8cf3306709e0cf7a2a0f"
FIELDS = {
    "forecast_runs": ("run_id", "experiment_id", "snapshot_id", "protocol_hash", "config_hash",
                      "code_sha", "upstream_sha", "environment", "started_at", "ended_at", "status", "supersedes_run_id"),
    "forecast_attempts": ("run_id", "model_id", "origin", "series_id", "attempt_no", "status",
                          "error_class", "safe_error_message", "query_id", "queue_seconds",
                          "compute_seconds", "wall_seconds", "retry_reason"),
    "forecast_values": ("run_id", "model_id", "origin", "series_id", "ds", "lead_day", "prediction",
                        "lower", "upper", "interval_level", "raw_prediction", "raw_lower",
                        "raw_upper", "transformed", "is_fallback"),
    "evaluation_cells": ("run_id", "model_id", "origin", "series_id", "horizon_days", "n_expected",
                         "n_actual", "n_predictions", "paired_status", "abs_error_sum", "actual_sum",
                         "signed_error_sum", "mase_denominator", "interval_n", "interval_hits",
                         "interval_width_sum", "interval_score_sum"),
}
KEYS = {
    "forecast_runs": ("run_id",),
    "forecast_attempts": ("run_id", "model_id", "origin", "series_id", "attempt_no"),
    "forecast_values": ("run_id", "model_id", "origin", "series_id", "ds"),
    "evaluation_cells": ("run_id", "model_id", "origin", "series_id", "horizon_days"),
}
SCHEMAS = {
    "forecast_runs": "run_id STRING, experiment_id STRING, snapshot_id STRING, protocol_hash STRING, config_hash STRING, code_sha STRING, upstream_sha STRING, environment STRING, started_at STRING, ended_at STRING, status STRING, supersedes_run_id STRING",
    "forecast_attempts": "run_id STRING, model_id STRING, origin STRING, series_id STRING, attempt_no INT, status STRING, error_class STRING, safe_error_message STRING, query_id STRING, queue_seconds DOUBLE, compute_seconds DOUBLE, wall_seconds DOUBLE, retry_reason STRING",
    "forecast_values": "run_id STRING, model_id STRING, origin STRING, series_id STRING, ds STRING, lead_day INT, prediction DOUBLE, lower DOUBLE, upper DOUBLE, interval_level DOUBLE, raw_prediction DOUBLE, raw_lower DOUBLE, raw_upper DOUBLE, transformed BOOLEAN, is_fallback BOOLEAN",
    "evaluation_cells": "run_id STRING, model_id STRING, origin STRING, series_id STRING, horizon_days INT, n_expected INT, n_actual INT, n_predictions INT, paired_status STRING, abs_error_sum DOUBLE, actual_sum DOUBLE, signed_error_sum DOUBLE, mase_denominator DOUBLE, interval_n INT, interval_hits INT, interval_width_sum DOUBLE, interval_score_sum DOUBLE",
}


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def transform(source: dict) -> dict[str, list[dict]]:
    if source.get("status") != STATUS or not source.get("run_id", "").startswith("development-slice-"):
        raise ValueError("Only the labeled development smoke slice can be persisted")
    if source.get("expected_cells") != 12 or source.get("complete_cells") != 12 or source.get("paired_local_cells") != 6:
        raise ValueError("Incomplete local smoke grid")
    if len(source["attempts"]) != 12 or len(source["evaluation_cells"]) != 12 or len(source["forecast_values"]) != 336:
        raise ValueError("Unexpected smoke row counts")
    run_id = source["run_id"]
    config = {"prophet_parameter_source": source["prophet_parameter_source"],
              "prophet_parameters": source["prophet_parameters"], "models": sorted(MODELS),
              "origins": source["origins"], "series_ids": source["series_ids"]}
    config_hash = _hash(json.dumps(config, sort_keys=True, separators=(",", ":")).encode())
    run = dict(zip(FIELDS["forecast_runs"], (
        run_id, "nyc311-development-smoke", source["silver_snapshot_id"],
        None, config_hash, source["code_sha"], UPSTREAM_SHA, "local_development_smoke",
        source["generated_at_utc"], source["generated_at_utc"], STATUS, None)))
    attempts = []
    values = []
    cells = []
    for item in source["attempts"]:
        if item["model_id"] not in MODELS or item["status"] != "success" or item["attempt_no"] != 1:
            raise ValueError("Unexpected smoke model/attempt status")
        attempts.append({"run_id": run_id, "model_id": item["model_id"], "origin": item["origin"],
                         "series_id": item["series_id"], "attempt_no": 1, "status": "success",
                         "error_class": None, "safe_error_message": None, "query_id": None,
                         "queue_seconds": None, "compute_seconds": None,
                         "wall_seconds": item["wall_seconds"], "retry_reason": None})
    for item in source["forecast_values"]:
        if item["model_id"] not in MODELS or item["lead_day"] not in range(1, 29):
            raise ValueError("Unexpected smoke forecast")
        if date.fromisoformat(item["ds"]) != date.fromisoformat(item["origin"]) + timedelta(days=item["lead_day"]):
            raise ValueError("Forecast date/lead mismatch")
        interval = item["lower"] is not None and item["upper"] is not None
        if (item["lower"] is None) != (item["upper"] is None):
            raise ValueError("Partial forecast interval")
        values.append({"run_id": run_id, "model_id": item["model_id"], "origin": item["origin"],
                       "series_id": item["series_id"], "ds": item["ds"], "lead_day": item["lead_day"],
                       "prediction": item["prediction"], "lower": item["lower"], "upper": item["upper"],
                       "interval_level": 0.8 if interval else None, "raw_prediction": item["raw_prediction"],
                       "raw_lower": item["raw_lower"], "raw_upper": item["raw_upper"],
                       "transformed": item["transformed"], "is_fallback": False})
    for item in source["evaluation_cells"]:
        metric = item["metrics"]
        if item["model_id"] not in MODELS or metric["n"] != 28:
            raise ValueError("Unexpected smoke score")
        cells.append({"run_id": run_id, "model_id": item["model_id"], "origin": item["origin"],
                      "series_id": item["series_id"], "horizon_days": 28, "n_expected": 28,
                      "n_actual": 28, "n_predictions": 28, "paired_status": "complete_local_smoke",
                      "abs_error_sum": metric["abs_error_sum"], "actual_sum": metric["actual_sum"],
                      "signed_error_sum": metric["signed_error_sum"],
                      "mase_denominator": metric["mase_denominator"], "interval_n": metric["interval_n"],
                      "interval_hits": metric["interval_hits"], "interval_width_sum": metric["interval_width_sum"],
                      "interval_score_sum": metric["interval_score_sum"]})
    result = {"forecast_runs": [run], "forecast_attempts": attempts,
              "forecast_values": values, "evaluation_cells": cells}
    attempt_keys = {tuple(row[k] for k in KEYS["forecast_attempts"][:-1]) for row in attempts}
    value_cells = Counter(tuple(row[k] for k in ("run_id", "model_id", "origin", "series_id")) for row in values)
    cell_keys = {tuple(row[k] for k in ("run_id", "model_id", "origin", "series_id")) for row in cells}
    if attempt_keys != cell_keys or any(value_cells[key] != 28 for key in cell_keys) or set(value_cells) != cell_keys:
        raise ValueError("Attempt/value/score grids differ")
    for table, rows in result.items():
        keys = [tuple(row[key] for key in KEYS[table]) for row in rows]
        if len(set(keys)) != len(keys):
            raise ValueError(f"Duplicate {table} keys")
    return result


def stage(source_path: Path, output_dir: Path) -> dict:
    source_bytes = source_path.read_bytes()
    source = json.loads(source_bytes)
    rows_by_table = transform(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"stage_id": output_dir.name, "run_id": source["run_id"], "status": STATUS,
                "source_sha256": _hash(source_bytes), "tables": {}}
    for table, rows in rows_by_table.items():
        payload = "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows).encode()
        path = output_dir / f"{table}.jsonl"
        if path.exists() and path.read_bytes() != payload:
            raise ValueError(f"Existing stage differs: {path}")
        path.write_bytes(payload)
        manifest["tables"][table] = {"rows": len(rows), "sha256": _hash(payload)}
    content = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    path = output_dir / "manifest.json"
    if path.exists() and path.read_bytes() != content:
        raise ValueError("Existing stage manifest differs")
    path.write_bytes(content)
    return manifest
