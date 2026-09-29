"""The tuning runner must resume without refitting and reject holdout rows."""

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from nyc311_forecast.development_tuning import run_tuning
from nyc311_forecast.models.prophet_adapter import ProphetParameters, TuningResult

SERIES = [f"BOROUGH|family-{index}" for index in range(21)]
SHA = "a" * 40


def inputs(tmp_path: Path, *, holdout: bool = False) -> tuple[Path, Path]:
    selection = tmp_path / "selection.json"
    silver = tmp_path / "daily.jsonl"
    selection.write_text(
        json.dumps({"candidates": [{"series_id": sid, "selected": True} for sid in SERIES]}),
        encoding="utf-8",
    )
    dates = ["2024-01-01", "2025-01-01"] if holdout else ["2024-01-01"]
    silver.write_text(
        "".join(json.dumps({"series_id": SERIES[0], "ds": ds, "y": 2}) + "\n" for ds in dates),
        encoding="utf-8",
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "snapshot_id": "synthetic-test",
                "series_manifest_hash": hashlib.sha256(selection.read_bytes()).hexdigest(),
                "daily_payload_hash": hashlib.sha256(silver.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    return selection, silver


def test_resume_keeps_trials_and_does_not_refit(tmp_path):
    selection, silver = inputs(tmp_path)
    calls = []

    def tuner(rows, *, series_id, n_trials, seed):
        calls.append((series_id, n_trials, seed, rows[-1]["ds"]))
        return TuningResult(
            series_id,
            ProphetParameters(0.05, 1.0, "additive"),
            0.1,
            tuple({"number": i, "state": "COMPLETE", "value": 0.1} for i in range(n_trials)),
            0.2,
            seed,
        )

    output = tmp_path / "tuning"
    first = run_tuning(
        selection, silver, output, code_sha=SHA, n_trials=5, series_limit=1, tuner=tuner
    )
    second = run_tuning(
        selection, silver, output, code_sha=SHA, n_trials=5, series_limit=1, tuner=tuner
    )
    assert first["results"][0]["status"] == "completed"
    assert second["results"][0]["status"] == "resumed"
    assert calls == [(SERIES[0], 5, 42, date(2024, 1, 1))]
    assert len(json.loads((output / "series-00.json").read_text())["trials"]) == 5
    with pytest.raises(ValueError, match="Existing checkpoint differs"):
        run_tuning(selection, silver, output, code_sha="b" * 40, n_trials=5, series_limit=1)


def test_tuning_rejects_holdout_and_unregistered_budget(tmp_path):
    selection, silver = inputs(tmp_path, holdout=True)
    with pytest.raises(ValueError, match="2025"):
        run_tuning(selection, silver, tmp_path / "tuning", code_sha=SHA, n_trials=5, series_limit=1)
    with pytest.raises(ValueError, match="20-trial"):
        run_tuning(selection, silver, tmp_path / "other", code_sha=SHA, n_trials=4)
