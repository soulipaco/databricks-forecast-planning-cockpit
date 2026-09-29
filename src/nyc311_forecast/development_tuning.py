"""Checkpointed, development-only Prophet tuning from the verified Silver snapshot."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import date
from pathlib import Path

from nyc311_forecast.models.prophet_adapter import TuningResult, tune_series


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _write_once(path: Path, value: dict) -> None:
    payload = _json_bytes(value)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"Existing checkpoint differs: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)


def run_tuning(
    selection_path: Path,
    silver_path: Path,
    output_dir: Path,
    *,
    code_sha: str,
    n_trials: int = 20,
    series_limit: int | None = None,
    tuner: Callable = tune_series,
) -> dict:
    """Run one selected series at a time and retain immutable trial checkpoints.

    A partial directory is resumable only with the same manifest. Forecast
    evaluation and 2025 data are deliberately outside this command.
    """
    if not (
        (n_trials == 20 and series_limit is None) or (n_trials == 5 and series_limit is not None)
    ):
        raise ValueError("Only registered 20-trial tuning or bounded 5-trial smoke is allowed")
    if series_limit is not None and not 1 <= series_limit <= 3:
        raise ValueError("Smoke series_limit must be 1 through 3")
    if len(code_sha) != 40 or any(ch not in "0123456789abcdef" for ch in code_sha):
        raise ValueError("A full lowercase Git SHA is required")
    selection_bytes = selection_path.read_bytes()
    silver_bytes = silver_path.read_bytes()
    silver_manifest = json.loads((silver_path.parent / "manifest.json").read_text(encoding="utf-8"))
    if (
        silver_manifest.get("status") != "complete"
        or silver_manifest.get("series_manifest_hash")
        != hashlib.sha256(selection_bytes).hexdigest()
        or silver_manifest.get("daily_payload_hash") != hashlib.sha256(silver_bytes).hexdigest()
    ):
        raise ValueError("Silver snapshot and selected-series manifest do not reconcile")
    selection = json.loads(selection_bytes)
    selected = [row["series_id"] for row in selection["candidates"] if row["selected"]]
    if len(selected) != 21 or len(set(selected)) != 21:
        raise ValueError("Expected the verified 21 unique selected series")
    if series_limit is not None:
        selected = selected[:series_limit]
    manifest = {
        "status": "development_tuning_smoke" if n_trials == 5 else "development_tuning",
        "code_sha": code_sha,
        "selection_sha256": hashlib.sha256(selection_bytes).hexdigest(),
        "silver_sha256": hashlib.sha256(silver_bytes).hexdigest(),
        "silver_snapshot_id": silver_manifest["snapshot_id"],
        "series_ids": selected,
        "n_trials": n_trials,
        "seed": 42,
        "inner_origins": ["2024-01-31", "2024-05-31", "2024-09-30"],
    }
    wanted = set(selected)
    by_series: dict[str, list[dict]] = {series_id: [] for series_id in selected}
    for line in silver_bytes.splitlines():
        row = json.loads(line)
        if row["series_id"] in wanted:
            ds = date.fromisoformat(row["ds"])
            if ds.year > 2024:
                raise ValueError("Tuning input includes the 2025 evaluation year")
            by_series[row["series_id"]].append({"ds": ds, "y": row["y"]})
    _write_once(output_dir / "manifest.json", manifest)
    results = []
    for index, series_id in enumerate(selected):
        path = output_dir / f"series-{index:02d}.json"
        if path.exists():
            prior = json.loads(path.read_text(encoding="utf-8"))
            if prior.get("series_id") != series_id or prior.get("n_trials") != n_trials:
                raise ValueError(f"Checkpoint identity mismatch: {path}")
            if prior.get("status") != "complete" or len(prior.get("trials", [])) != n_trials:
                raise ValueError(f"Incomplete checkpoint: {path}")
            results.append({"series_id": series_id, "status": "resumed"})
            continue
        rows = by_series[series_id]
        if not rows or max(row["ds"] for row in rows) > date(2024, 12, 31):
            raise ValueError(f"Invalid development history for {series_id}")
        result: TuningResult = tuner(rows, series_id=series_id, n_trials=n_trials, seed=42)
        if result.series_id != series_id or len(result.trials) != n_trials:
            raise ValueError(f"Tuning result does not match planned trials: {series_id}")
        checkpoint = {
            "status": "complete",
            "series_id": series_id,
            "n_trials": n_trials,
            "parameters": asdict(result.parameters),
            "pooled_wape": result.pooled_wape,
            "trials": list(result.trials),
            "wall_seconds": result.wall_seconds,
            "seed": result.seed,
        }
        _write_once(path, checkpoint)
        results.append({"series_id": series_id, "status": "completed"})
    summary = {"manifest": manifest, "results": results}
    # The summary is deterministic across resumed and first runs except status.
    return summary
