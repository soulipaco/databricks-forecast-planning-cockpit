"""Synthetic checks for full-grid development comparison and tuning provenance."""

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from nyc311_forecast.development_compare import STATUS, load_inputs, run_comparison
from nyc311_forecast.models.contracts import ForecastResult, publish_prediction
from nyc311_forecast.models.prophet_adapter import ProphetParameters

ORIGINS = (date(2024, 10, 31), date(2024, 11, 30))
PARAMETERS = ProphetParameters(0.05, 1.0, "additive")


def _series_rows():
    first = date(2021, 10, 1)
    last = date(2024, 12, 28)
    return [
        {"ds": first + timedelta(days=i), "y": float(10 + i % 7)}
        for i in range((last - first).days + 1)
    ]


def _adapter(model_id, *, fail_on=None, incomplete=False):
    def forecast(history, dates, *, series_id, origin, model_config, execution_context):
        assert len(history) == 1095
        assert history[-1]["ds"] == origin
        assert dates == [origin + timedelta(days=i) for i in range(1, 29)]
        if model_id == "prophet_tuned":
            assert model_config == PARAMETERS
        if fail_on == (series_id, origin):
            raise RuntimeError("synthetic fit failure")
        values = tuple(
            publish_prediction(
                ds,
                lead,
                10.0,
                raw_lower=8.0 if model_id == "prophet_tuned" else None,
                raw_upper=12.0 if model_id == "prophet_tuned" else None,
                interval_level=0.8 if model_id == "prophet_tuned" else None,
            )
            for lead, ds in enumerate(dates[:27] if incomplete else dates, 1)
        )
        if incomplete:
            return SimpleNamespace(
                model_id=model_id,
                series_id=series_id,
                origin=origin,
                predictions=values,
                wall_seconds=0.1,
            )
        return ForecastResult(model_id, series_id, origin, values, wall_seconds=0.1)

    return SimpleNamespace(forecast=forecast)


def test_two_model_grid_keeps_failure_visible_and_excludes_its_values():
    ids = ("series-a", "series-b")
    result = run_comparison(
        ids,
        {series_id: _series_rows() for series_id in ids},
        {series_id: PARAMETERS for series_id in ids},
        adapters={
            "snaive7": _adapter("snaive7"),
            "prophet_tuned": _adapter("prophet_tuned", fail_on=("series-b", ORIGINS[1])),
        },
    )
    assert result["status"] == STATUS
    assert result["model_ids"] == ["snaive7", "prophet_tuned"]
    assert result["origins"] == [day.isoformat() for day in ORIGINS]
    assert (result["expected_cells"], result["complete_cells"], result["failed_cells"]) == (8, 7, 1)
    assert result["paired_two_model_cells"] == 3
    assert len(result["attempts"]) == len(result["evaluation_cells"]) == 8
    assert len(result["forecast_values"]) == 7 * 28
    failed = [row for row in result["evaluation_cells"] if row["status"] == "failed"]
    assert failed == [
        {
            "origin": "2024-11-30",
            "series_id": "series-b",
            "model_id": "prophet_tuned",
            "horizon_days": 28,
            "n_expected": 28,
            "n_actual": 28,
            "n_predictions": 0,
            "status": "failed",
            "error_class": "RuntimeError",
        }
    ]


def test_incomplete_adapter_output_cannot_enter_scores():
    result = run_comparison(
        ("series-a",),
        {"series-a": _series_rows()},
        {"series-a": PARAMETERS},
        adapters={
            "snaive7": _adapter("snaive7"),
            "prophet_tuned": _adapter("prophet_tuned", incomplete=True),
        },
    )
    assert result["complete_cells"] == 2
    assert result["paired_two_model_cells"] == 0
    assert len(result["forecast_values"]) == 56
    assert all(
        row["n_predictions"] == 27
        for row in result["evaluation_cells"]
        if row["model_id"] == "prophet_tuned"
    )


def test_run_rejects_missing_per_series_parameters():
    with pytest.raises(ValueError, match="Every series"):
        run_comparison(("series-a",), {"series-a": _series_rows()}, {})


def _write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_input_loader_rejects_incomplete_20_trial_grid(tmp_path):
    selection_path = tmp_path / "selection.json"
    silver_path = tmp_path / "silver" / "daily_requests.jsonl"
    tuning_dir = tmp_path / "tuning"
    ids = [f"series-{i:02d}" for i in range(21)]
    selection_sha = _write_json(
        selection_path,
        {
            "candidates": [{"series_id": series_id, "selected": True} for series_id in ids],
        },
    )
    silver_path.parent.mkdir(parents=True)
    silver_path.write_text("", encoding="utf-8")
    silver_sha = hashlib.sha256(b"").hexdigest()
    _write_json(
        silver_path.parent / "manifest.json",
        {
            "status": "complete",
            "series_manifest_hash": selection_sha,
            "daily_payload_hash": silver_sha,
            "snapshot_id": "synthetic",
        },
    )
    _write_json(
        tuning_dir / "manifest.json",
        {
            "status": "development_tuning",
            "n_trials": 20,
            "seed": 42,
            "series_ids": ids,
            "selection_sha256": selection_sha,
            "silver_sha256": silver_sha,
            "silver_snapshot_id": "synthetic",
            "inner_origins": ["2024-01-31", "2024-05-31", "2024-09-30"],
        },
    )
    with pytest.raises(FileNotFoundError):
        load_inputs(selection_path, silver_path, tuning_dir)
