"""Protocol freeze gate: refuse to freeze until every development prerequisite exists.

The gate reads only 2021-2024 development artifacts. It never retrieves 2025 data and
never treats a two-model development run as a substitute for the three-model grid.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from nyc311_forecast.config import MODELS
from nyc311_forecast.evaluation.splits import DEVELOPMENT_ORIGINS

EVALUATION_START = date(2025, 1, 1)
INNER_ORIGINS = ["2024-01-31", "2024-05-31", "2024-09-30"]
N_TRIALS = 20


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_selection(path: Path, blockers: list[str]) -> list[str]:
    if not path.exists():
        blockers.append(f"series manifest missing: {path.name}")
        return []
    selection = _load(path)
    series_ids = [row["series_id"] for row in selection["candidates"] if row["selected"]]
    if not series_ids or len(series_ids) != len(set(series_ids)):
        blockers.append("series manifest has no selected series or duplicate series IDs")
    if not str(selection.get("snapshot_id", "")).startswith("selection-2021-2023"):
        blockers.append("series manifest is not derived from the 2021-2023 selection snapshot")
    return series_ids


def _check_tuning(tuning_dir: Path, series_ids: list[str], blockers: list[str]) -> None:
    manifest_path = tuning_dir / "manifest.json"
    if not manifest_path.exists():
        blockers.append("Prophet tuning manifest missing")
        return
    manifest = _load(manifest_path)
    if manifest.get("series_ids") != series_ids:
        blockers.append("tuning series do not match the selected series manifest")
    if manifest.get("n_trials") != N_TRIALS or manifest.get("inner_origins") != INNER_ORIGINS:
        blockers.append("tuning budget or inner origins differ from protocol v1")
    incomplete = []
    for index, series_id in enumerate(series_ids):
        path = tuning_dir / f"series-{index:02d}.json"
        checkpoint = _load(path) if path.exists() else {}
        trials = checkpoint.get("trials", [])
        if (
            checkpoint.get("status") != "complete"
            or checkpoint.get("series_id") != series_id
            or len(trials) != N_TRIALS
            or not checkpoint.get("parameters")
        ):
            incomplete.append(series_id)
    if incomplete:
        blockers.append(f"{len(incomplete)} series lack a complete {N_TRIALS}-trial checkpoint")


def _check_development_run(path: Path, series_ids: list[str], blockers: list[str]) -> None:
    if not path.exists():
        blockers.append(f"development run missing: {path.name}")
        return
    run = _load(path)
    missing_models = [m for m in MODELS if m not in run.get("model_ids", [])]
    if missing_models:
        blockers.append(
            "development run lacks candidate(s) "
            + ", ".join(missing_models)
            + "; a two-model run cannot freeze the three-model protocol"
        )
    if run.get("origins") != [origin.isoformat() for origin in DEVELOPMENT_ORIGINS]:
        blockers.append("development run origins differ from protocol v1")
    expected = len(series_ids) * len(DEVELOPMENT_ORIGINS) * len(MODELS)
    cells = run.get("evaluation_cells", [])
    complete = {
        (c["series_id"], c["origin"], c["model_id"])
        for c in cells
        if c.get("status") == "complete"
    }
    required = {
        (s, o.isoformat(), m) for s in series_ids for o in DEVELOPMENT_ORIGINS for m in MODELS
    }
    if len(complete & required) != expected:
        blockers.append(
            f"development grid has {len(complete & required)}/{expected} complete "
            "three-model cells"
        )
    late = [
        v["ds"]
        for v in run.get("forecast_values", [])
        if date.fromisoformat(v["ds"]) >= EVALUATION_START
    ]
    if late:
        blockers.append(f"development run contains {len(late)} rows dated in the 2025 holdout")


def check_freeze_readiness(
    *,
    series_manifest: Path,
    tuning_dir: Path,
    development_run: Path,
    protocol_path: Path,
    freeze_manifest: Path,
) -> dict[str, Any]:
    """Return every unmet freeze prerequisite; an empty list means ready."""
    blockers: list[str] = []
    if freeze_manifest.exists():
        blockers.append("a freeze manifest already exists; freezing is not repeatable")
    if not protocol_path.exists():
        blockers.append(f"protocol document missing: {protocol_path.name}")
    series_ids = _check_selection(series_manifest, blockers)
    if series_ids:
        _check_tuning(tuning_dir, series_ids, blockers)
        _check_development_run(development_run, series_ids, blockers)
    return {"ready": not blockers, "blockers": blockers, "n_series": len(series_ids)}


def write_freeze_manifest(
    *,
    series_manifest: Path,
    tuning_dir: Path,
    development_run: Path,
    protocol_path: Path,
    config_path: Path,
    freeze_manifest: Path,
    code_sha: str,
    protocol_version: str,
) -> dict[str, Any]:
    """Write the hash manifest only when the readiness check reports no blockers."""
    report = check_freeze_readiness(
        series_manifest=series_manifest,
        tuning_dir=tuning_dir,
        development_run=development_run,
        protocol_path=protocol_path,
        freeze_manifest=freeze_manifest,
    )
    if not report["ready"]:
        raise ValueError("Freeze refused: " + "; ".join(report["blockers"]))
    manifest = {
        "status": "frozen",
        "protocol_version": protocol_version,
        "code_sha": code_sha,
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "hashes": {
            "protocol": _sha(protocol_path),
            "config": _sha(config_path),
            "series_manifest": _sha(series_manifest),
            "tuning_manifest": _sha(tuning_dir / "manifest.json"),
            "development_run": _sha(development_run),
        },
        "models": list(MODELS),
        "n_series": report["n_series"],
    }
    freeze_manifest.parent.mkdir(parents=True, exist_ok=True)
    with freeze_manifest.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest
