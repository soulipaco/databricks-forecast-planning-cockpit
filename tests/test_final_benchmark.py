"""Final stage guards: frozen-input hashes and summary arithmetic on a synthetic grid."""

import hashlib
import json

import pytest

from nyc311_forecast.config import MODELS
from nyc311_forecast.final_benchmark import summarize_final, verify_freeze


def _freeze(tmp_path, files):
    manifest = {"status": "frozen", "models": list(MODELS), "hashes": {
        name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()}}
    path = tmp_path / "freeze.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_changed_frozen_input_refuses_every_final_stage(tmp_path):
    protocol = tmp_path / "protocol.md"
    protocol.write_text("v1", encoding="utf-8")
    files = {"protocol": protocol}
    freeze = _freeze(tmp_path, files)
    assert verify_freeze(freeze, files)["status"] == "frozen"
    protocol.write_text("v1 edited after seeing 2025", encoding="utf-8")
    with pytest.raises(ValueError, match="protocol"):
        verify_freeze(freeze, files)


def _metrics(abs_error, actual, signed=0.0, interval=False):
    return {"n": 28, "abs_error_sum": abs_error, "actual_sum": actual,
            "signed_error_sum": signed, "wape": abs_error / actual,
            "signed_bias": signed / actual, "mase_denominator": 1.0, "mase": 1.0,
            "interval_n": 28 if interval else 0, "interval_hits": 21 if interval else 0,
            "interval_width_sum": 56.0 if interval else 0.0, "interval_score_sum": 0.0}


def test_summary_scores_paired_cells_windows_and_frozen_policy():
    errors = {"snaive7": 3.0, "prophet_tuned": 2.0, "ai_forecast_v2": 1.0}
    origins = ["2024-12-31", "2025-01-31"]
    cells, values = [], []
    for series in ("A", "B"):
        for origin in origins:
            for model, per_day in errors.items():
                cells.append({"model_id": model, "series_id": series, "origin": origin,
                              "status": "complete",
                              "metrics": _metrics(per_day * 28, 280.0, -per_day * 28,
                                                  model != "snaive7")})
                values.extend({"model_id": model, "series_id": series, "origin": origin,
                               "lead_day": lead, "actual": 10.0,
                               "prediction": 10.0 - per_day} for lead in range(1, 29))
    combined = {"run_id": "r", "series_ids": ["A", "B"], "origins": origins,
                "evaluation_cells": cells, "forecast_values": values}
    summary = summarize_final(combined, {"A": "prophet_tuned", "B": "snaive7"})
    native = summary["models"]["ai_forecast_v2"]
    assert native["primary_median_series_wape"] == pytest.approx(0.1)
    assert native["pooled_wape_by_lead_window"]["1-7"] == pytest.approx(0.1)
    assert native["interval_coverage"] == pytest.approx(0.75)
    assert summary["practically_competitive_rule"]["meets_practically_competitive_rule"]
    # Policy mixes Prophet (0.2) on A and naive (0.3) on B from frozen development choices.
    assert summary["frozen_development_champion_policy"]["pooled_wape"] == pytest.approx(0.25)
    assert summary["series_lowest_wape_counts"]["ai_forecast_v2"] == 2


def test_final_inputs_use_2025_silver_with_development_tuning_lineage():
    from nyc311_forecast.development_compare import SILVER_PATH, load_inputs
    from nyc311_forecast.final_benchmark import EVAL_SILVER

    series_ids, by_series, parameters, provenance = load_inputs(
        silver_path=EVAL_SILVER, last_year=2025, tuning_silver_path=SILVER_PATH
    )
    assert provenance["silver_snapshot_id"] == "evaluation-silver-20260929"
    assert len(parameters) == 21
    assert max(row["ds"] for row in by_series[series_ids[0]]).isoformat() == "2025-12-31"
    with pytest.raises(ValueError, match="after 2024"):
        load_inputs(silver_path=EVAL_SILVER)
