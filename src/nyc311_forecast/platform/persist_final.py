"""Validate and stage the frozen final three-model benchmark into contract-v1 table rows."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from nyc311_forecast.config import MODELS
from nyc311_forecast.evaluation.splits import FINAL_ORIGINS
from nyc311_forecast.platform.persist_smoke import FIELDS, UPSTREAM_SHA

STATUS = "final_three_model_benchmark"
RUN_ID = re.compile(r"final-three-model-[0-9a-f]{12}\Z")
ORIGINS = tuple(origin.isoformat() for origin in FINAL_ORIGINS)


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _finite(value, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} is not finite")
    return number


def transform(source: dict, *, protocol_hash: str, config_hash: str) -> tuple[dict, dict]:
    if source.get("status") != STATUS or not RUN_ID.fullmatch(source.get("run_id", "")):
        raise ValueError("Only the labeled final three-model benchmark is allowed")
    if source.get("model_ids") != list(MODELS) or source.get("origins") != list(ORIGINS):
        raise ValueError("Unexpected model/origin grid")
    series = source["series_ids"]
    expected = {(o, s, m) for o in ORIGINS for s in series for m in MODELS}
    run_id = source["run_id"]
    run = dict(zip(FIELDS["forecast_runs"], (
        run_id, "nyc311-benchmark-v1", source["silver_snapshot_id"], protocol_hash,
        config_hash, source["code_sha_by_source"]["native"], UPSTREAM_SHA,
        "local naive/Prophet + Databricks trial SQL warehouse ai_forecast v2",
        None, None, STATUS, None)))
    attempts = []
    attempt_keys = set()
    for item in source["attempts"]:
        key = (item["origin"], item["series_id"], item["model_id"])
        full = (*key, item["attempt_no"])
        if key not in expected or full in attempt_keys:
            raise ValueError("Attempt grid has a duplicate or unexpected key")
        attempt_keys.add(full)
        metrics = item.get("query_metrics") or {}
        attempts.append({
            "run_id": run_id, "model_id": key[2], "origin": key[0], "series_id": key[1],
            "attempt_no": item["attempt_no"], "status": item["status"],
            "error_class": item.get("error_class"),
            "safe_error_message": item.get("safe_error_message"),
            "query_id": item.get("query_id"), "queue_seconds": None,
            "compute_seconds": metrics["execution_time_ms"] / 1000
            if metrics.get("execution_time_ms") is not None else None,
            "wall_seconds": item.get("wall_seconds"),
            "retry_reason": "transient" if item["attempt_no"] > 1 else None,
        })
    cells, successful = [], set()
    for item in source["evaluation_cells"]:
        key = (item["origin"], item["series_id"], item["model_id"])
        if key not in expected:
            raise ValueError("Unexpected evaluation cell")
        metric = item.get("metrics") if item["status"] == "complete" else None
        if metric:
            if metric.get("n") != 28:
                raise ValueError("Complete cell lacks a full horizon")
            successful.add(key)
        cells.append({
            "run_id": run_id, "model_id": key[2], "origin": key[0], "series_id": key[1],
            "horizon_days": 28, "n_expected": 28, "n_actual": item["n_actual"],
            "n_predictions": item["n_predictions"],
            "paired_status": "complete" if metric else "failed",
            **{name: (_finite(metric[name], name) if metric else None) for name in (
                "abs_error_sum", "actual_sum", "signed_error_sum", "mase_denominator",
                "interval_width_sum", "interval_score_sum")},
            "interval_n": metric["interval_n"] if metric else None,
            "interval_hits": metric["interval_hits"] if metric else None,
        })
    if {(c["origin"], c["series_id"], c["model_id"]) for c in cells} != expected:
        raise ValueError("Incomplete final evaluation grid")
    values, by_cell = [], Counter()
    for item in source["forecast_values"]:
        key = (item["origin"], item["series_id"], item["model_id"])
        if key not in successful:
            raise ValueError("Forecast row outside a complete cell")
        if date.fromisoformat(item["ds"]) != date.fromisoformat(item["origin"]) + timedelta(
            days=item["lead_day"]
        ):
            raise ValueError("Forecast date/lead mismatch")
        by_cell[key] += 1
        values.append({
            "run_id": run_id, "model_id": key[2], "origin": key[0], "series_id": key[1],
            "ds": item["ds"], "lead_day": item["lead_day"],
            "prediction": _finite(item["prediction"], "prediction"),
            "lower": item["lower"], "upper": item["upper"],
            "interval_level": item["interval_level"], "raw_prediction": item["raw_prediction"],
            "raw_lower": item["raw_lower"], "raw_upper": item["raw_upper"],
            "transformed": item["transformed"], "is_fallback": False,
        })
    if set(by_cell) != successful or any(n != 28 for n in by_cell.values()):
        raise ValueError("Successful cells do not each have 28 rows")
    rows = {"forecast_runs": [run], "forecast_attempts": attempts,
            "forecast_values": values, "evaluation_cells": cells}
    summary = {"expected_cells": len(expected), "complete_cells": len(successful),
               "failed_cells": len(expected) - len(successful)}
    return rows, summary


def stage(source_path: Path, output_dir: Path, *, protocol_hash: str, config_hash: str) -> dict:
    source_bytes = source_path.read_bytes()
    rows, summary = transform(json.loads(source_bytes), protocol_hash=protocol_hash,
                              config_hash=config_hash)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"stage_id": output_dir.name, "run_id": rows["forecast_runs"][0]["run_id"],
                "status": STATUS, "source_sha256": _hash(source_bytes), **summary, "tables": {}}
    for table, table_rows in rows.items():
        payload = "".join(
            json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in table_rows
        ).encode()
        path = output_dir / f"{table}.jsonl"
        if path.exists() and path.read_bytes() != payload:
            raise ValueError(f"Existing stage differs: {path}")
        path.write_bytes(payload)
        manifest["tables"][table] = {"rows": len(table_rows), "sha256": _hash(payload)}
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
