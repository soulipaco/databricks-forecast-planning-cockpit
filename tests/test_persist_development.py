"""Synthetic contract fixtures only; these are not model results."""

import copy
import importlib.util
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from nyc311_forecast.platform.persist_development import MODELS, ORIGINS, stage, transform


def fixture_output():
    series = [f"BOROUGH|Family {i:02d}" for i in range(21)]
    source = {
        "status": "partial_two_model_development_not_benchmark",
        "run_id": "development-two-model-" + "a" * 12,
        "code_sha": "a" * 40,
        "generated_at_utc": "2026-09-29T12:00:00+00:00",
        "silver_snapshot_id": "synthetic-contract-only",
        "silver_sha256": "b" * 64,
        "selection_sha256": "c" * 64,
        "tuning_manifest_sha256": "d" * 64,
        "tuning_checkpoint_sha256_by_series": {s: "e" * 64 for s in series},
        "prophet_parameters_by_series": {s: {"seasonality_mode": "additive"} for s in series},
        "model_ids": list(MODELS), "origins": list(ORIGINS), "series_ids": series,
        "expected_cells": 84, "complete_cells": 83, "failed_cells": 1,
        "paired_two_model_cells": 41,
        "attempts": [], "evaluation_cells": [], "forecast_values": [],
    }
    for origin in ORIGINS:
        for series_id in series:
            for model_id in MODELS:
                failed = (origin, series_id, model_id) == (ORIGINS[0], series[0], "prophet_tuned")
                key = {"origin": origin, "series_id": series_id, "model_id": model_id}
                source["attempts"].append({**key, "attempt_no": 1,
                    "status": "failed" if failed else "success",
                    **({"error_class": "RuntimeError", "safe_error_message": "fixture failure"}
                       if failed else {"wall_seconds": 1.0})})
                cell = {**key, "horizon_days": 28, "n_expected": 28,
                        "n_actual": 0 if failed else 28,
                        "n_predictions": 0 if failed else 28,
                        "status": "failed" if failed else "complete"}
                if failed:
                    cell["error_class"] = "RuntimeError"
                else:
                    cell["metrics"] = {"n": 28, "abs_error_sum": 28.0,
                        "actual_sum": 280.0, "signed_error_sum": 0.0,
                        "mase_denominator": 10.0, "interval_n": 28 if model_id == "prophet_tuned" else 0,
                        "interval_hits": 20 if model_id == "prophet_tuned" else 0,
                        "interval_width_sum": 100.0 if model_id == "prophet_tuned" else 0.0,
                        "interval_score_sum": 200.0 if model_id == "prophet_tuned" else 0.0}
                    for lead in range(1, 29):
                        ds = date.fromisoformat(origin) + timedelta(days=lead)
                        interval = model_id == "prophet_tuned"
                        source["forecast_values"].append({**key, "ds": ds.isoformat(),
                            "lead_day": lead, "actual": 10, "prediction": 10.0,
                            "raw_prediction": 10.0, "lower": 8.0 if interval else None,
                            "upper": 12.0 if interval else None,
                            "raw_lower": 8.0 if interval else None,
                            "raw_upper": 12.0 if interval else None,
                            "interval_level": 0.8 if interval else None,
                            "transformed": False, "is_fallback": False})
                source["evaluation_cells"].append(cell)
    return source


def test_failure_visible_and_full_grid_staged(tmp_path):
    source = fixture_output()
    rows, summary = transform(source)
    assert summary == {"expected_cells": 84, "complete_cells": 83,
                       "failed_cells": 1, "paired_two_model_cells": 41}
    assert len(rows["forecast_attempts"]) == len(rows["evaluation_cells"]) == 84
    assert len(rows["forecast_values"]) == 83 * 28
    failed = [r for r in rows["evaluation_cells"] if r["paired_status"] == "failed_two_model_development"]
    assert len(failed) == 1 and failed[0]["abs_error_sum"] is None
    source_path = tmp_path / "source.json"
    source_path.write_text(json.dumps(source))
    manifest = stage(source_path, tmp_path / "stage")
    assert manifest["tables"]["forecast_values"]["rows"] == 2324
    assert stage(source_path, tmp_path / "stage") == manifest


def test_missing_attempt_and_fallback_rejected():
    source = fixture_output()
    missing = copy.deepcopy(source)
    missing["attempts"].pop()
    with pytest.raises(ValueError, match="84 attempts"):
        transform(missing)
    fallback = copy.deepcopy(source)
    fallback["forecast_values"][0]["is_fallback"] = True
    with pytest.raises(ValueError, match="fallback"):
        transform(fallback)


def test_wrong_success_and_nonfinite_metric_rejected():
    source = fixture_output()
    mismatch = copy.deepcopy(source)
    mismatch["attempts"][0]["status"] = "failed"
    mismatch["attempts"][0]["error_class"] = "RuntimeError"
    with pytest.raises(ValueError, match="success sets"):
        transform(mismatch)
    bad_metric = copy.deepcopy(source)
    bad_metric["evaluation_cells"][0]["metrics"]["abs_error_sum"] = float("nan")
    with pytest.raises(ValueError, match="not finite"):
        transform(bad_metric)


def test_persist_sql_scoped_merge_and_exact_readback(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("persist_development_compare", scripts / "persist_development_compare.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    statements = []
    responses = iter([[[84, 0]], [[0]], None, [[84, 0, 0]]])

    def fake_query(_api, _warehouse, sql, **_kwargs):
        statements.append(sql)
        return f"query-{len(statements)}", next(responses)

    monkeypatch.setattr(module, "run_query", fake_query)
    result = module.persist_table(None, "warehouse", "cat.sch.evaluation_cells",
                                  "/Volumes/cat/sch/artifacts/stage/evaluation_cells.jsonl",
                                  "evaluation_cells", "development-two-model-" + "a" * 12, 84)
    assert result["query_ids"]["readback"] == "query-4"
    assert "WHEN NOT MATCHED THEN INSERT" in statements[2]
    assert "WHEN MATCHED" not in statements[2]
    assert "WHERE run_id = 'development-two-model-aaaaaaaaaaaa'" in statements[3]
    assert statements[3].count("EXCEPT ALL") == 2
