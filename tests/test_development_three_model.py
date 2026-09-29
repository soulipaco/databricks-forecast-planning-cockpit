"""Three-model development combination: identity checks, grid completeness and pairing."""

import pytest

from nyc311_forecast.development_three_model import combine, summarize

SERIES = ["BRONX|A", "QUEENS|B"]
ORIGINS = ["2024-10-31", "2024-11-30"]
HASHES = {"two_model": "a" * 64, "native": "b" * 64}


def _metrics(abs_error, actual=100.0, signed=0.0, hits=0, interval_n=0):
    return {"n": 28, "abs_error_sum": abs_error, "actual_sum": actual,
            "signed_error_sum": signed, "wape": abs_error / actual,
            "signed_bias": signed / actual, "mase_denominator": 1.0, "mase": 1.0,
            "interval_n": interval_n, "interval_hits": hits, "interval_width_sum": 0.0,
            "interval_score_sum": 0.0}


def _run(status, models, errors, **extra):
    cells = [
        {"origin": o, "series_id": s, "model_id": m, "status": "complete",
         "metrics": _metrics(errors[m], hits=20 if m != "snaive7" else 0,
                             interval_n=28 if m != "snaive7" else 0)}
        for o in ORIGINS for s in SERIES for m in models
    ]
    return {"status": status, "run_id": status, "code_sha": "c", "series_ids": SERIES,
            "origins": ORIGINS, "silver_sha256": "s", "silver_snapshot_id": "silver",
            "selection_sha256": "sel", "prophet_parameters_by_series": {}, "attempts": [],
            "evaluation_cells": cells, "forecast_values": [], **extra}


def _inputs(native_error=10.0):
    two = _run("partial_two_model_development_not_benchmark", ("snaive7", "prophet_tuned"),
               {"snaive7": 20.0, "prophet_tuned": 10.0})
    native = _run("native_v2_development_not_benchmark", ("ai_forecast_v2",),
                  {"ai_forecast_v2": native_error}, series_limit=None)
    return two, native


def test_combined_grid_pairs_all_three_models():
    combined = combine(*_inputs(), source_hashes=HASHES)
    assert (combined["expected_cells"], combined["complete_cells"]) == (12, 12)
    assert combined["paired_three_model_cells"] == 4
    report = summarize(combined)
    assert report["models"]["ai_forecast_v2"]["paired_pooled_wape"] == pytest.approx(0.1)
    assert report["models"]["ai_forecast_v2"]["interval_coverage"] == pytest.approx(20 / 28)
    # Equal WAPE: the simplicity order prefers native SQL over Prophet.
    assert report["champion_counts"]["ai_forecast_v2"] == 2
    assert report["practically_competitive_rule_on_development"]["meets_illustrative_rule"]


def test_native_more_than_five_percent_worse_is_not_competitive():
    report = summarize(combine(*_inputs(native_error=10.6), source_hashes=HASHES))
    rule = report["practically_competitive_rule_on_development"]
    assert rule["primary_wape_relative_to_prophet"] == pytest.approx(0.06)
    assert not rule["meets_illustrative_rule"]
    assert report["champion_counts"]["prophet_tuned"] == 2


def test_runs_on_different_snapshots_or_pilots_are_rejected():
    two, native = _inputs()
    with pytest.raises(ValueError, match="silver_sha256"):
        combine(two, {**native, "silver_sha256": "other"}, source_hashes=HASHES)
    with pytest.raises(ValueError, match="pilot"):
        combine(two, {**native, "series_limit": 1}, source_hashes=HASHES)


def test_missing_native_cell_breaks_the_grid():
    two, native = _inputs()
    native["evaluation_cells"] = native["evaluation_cells"][:-1]
    with pytest.raises(ValueError, match="three-model grid"):
        combine(two, native, source_hashes=HASHES)
