"""Freeze gate: synthetic prerequisites plus the real two-model development artifact."""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from nyc311_forecast.config import MODELS
from nyc311_forecast.freeze import check_freeze_readiness, write_freeze_manifest

ROOT = Path(__file__).resolve().parents[1]
SERIES = ["BRONX|A", "QUEENS|B"]
ORIGINS = ["2024-10-31", "2024-11-30"]


def _write(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _fixture(tmp_path: Path, *, models=MODELS, late_row=False, short_series=None):
    selection = _write(
        tmp_path / "selection.json",
        {
            "snapshot_id": "selection-2021-2023-synthetic",
            "candidates": [{"series_id": s, "selected": True} for s in SERIES]
            + [{"series_id": "BRONX|Z", "selected": False}],
        },
    )
    tuning = tmp_path / "tuning"
    _write(
        tuning / "manifest.json",
        {
            "series_ids": SERIES,
            "n_trials": 20,
            "inner_origins": ["2024-01-31", "2024-05-31", "2024-09-30"],
        },
    )
    for index, series_id in enumerate(SERIES):
        trials = 19 if series_id == short_series else 20
        _write(
            tuning / f"series-{index:02d}.json",
            {
                "series_id": series_id,
                "status": "complete",
                "parameters": {"changepoint_prior_scale": 0.05},
                "trials": [{"state": "COMPLETE"}] * trials,
            },
        )
    values = []
    for origin in ORIGINS:
        start = date.fromisoformat(origin)
        values.extend(
            {"ds": (start + timedelta(days=lead)).isoformat()} for lead in range(1, 29)
        )
    if late_row:
        values.append({"ds": "2025-01-02"})
    run = _write(
        tmp_path / "run.json",
        {
            "model_ids": list(models),
            "origins": ORIGINS,
            "evaluation_cells": [
                {"series_id": s, "origin": o, "model_id": m, "status": "complete"}
                for s in SERIES
                for o in ORIGINS
                for m in models
            ],
            "forecast_values": values,
        },
    )
    protocol = tmp_path / "protocol.md"
    protocol.write_text("# protocol v1\n", encoding="utf-8")
    return {
        "series_manifest": selection,
        "tuning_dir": tuning,
        "development_run": run,
        "protocol_path": protocol,
        "freeze_manifest": tmp_path / "freeze_manifest.json",
    }


def test_complete_three_model_development_is_ready_and_writes_once(tmp_path):
    paths = _fixture(tmp_path)
    assert check_freeze_readiness(**paths) == {"ready": True, "blockers": [], "n_series": 2}
    config = tmp_path / "benchmark.yaml"
    config.write_text("experiment_id: x\n", encoding="utf-8")
    manifest = write_freeze_manifest(
        **paths, config_path=config, code_sha="abc", protocol_version="1.0"
    )
    assert manifest["status"] == "frozen"
    assert set(manifest["hashes"]) == {
        "protocol", "config", "series_manifest", "tuning_manifest", "development_run"
    }
    with pytest.raises(ValueError, match="already exists"):
        write_freeze_manifest(**paths, config_path=config, code_sha="abc", protocol_version="1.0")


def test_two_model_run_cannot_freeze_three_model_protocol(tmp_path):
    paths = _fixture(tmp_path, models=("snaive7", "prophet_tuned"))
    report = check_freeze_readiness(**paths)
    assert not report["ready"]
    assert any("ai_forecast_v2" in b for b in report["blockers"])
    assert any("8/12" in b for b in report["blockers"])
    with pytest.raises(ValueError, match="Freeze refused"):
        write_freeze_manifest(
            **paths, config_path=paths["protocol_path"], code_sha="abc", protocol_version="1.0"
        )
    assert not paths["freeze_manifest"].exists()


def test_holdout_dates_and_incomplete_tuning_block_freeze(tmp_path):
    report = check_freeze_readiness(**_fixture(tmp_path, late_row=True, short_series="QUEENS|B"))
    assert any("2025 holdout" in b for b in report["blockers"])
    assert any("1 series lack" in b for b in report["blockers"])


def test_real_two_model_development_artifact_is_blocked_only_by_missing_v2(tmp_path):
    report = check_freeze_readiness(
        series_manifest=ROOT / "data/series_manifest/selection-v1.json",
        tuning_dir=ROOT / "evidence/development_tuning_full_20260929",
        development_run=ROOT / "evidence/development_two_model_full_20260929.json",
        protocol_path=ROOT / "docs/design/03_BENCHMARK_PROTOCOL.md",
        freeze_manifest=tmp_path / "freeze_manifest.json",
    )
    assert report["n_series"] == 21
    assert report["blockers"] == [
        (
            "development run lacks candidate(s) ai_forecast_v2; "
            "a two-model run cannot freeze the three-model protocol"
        ),
        "development grid has 84/126 complete three-model cells",
    ]
