"""Paired diagnostic arithmetic uses identical complete cells for each model."""

import pytest

from nyc311_forecast.evaluation.development_report import summarize


def test_paired_ratio_of_sums_excludes_unpaired_cell():
    origins = ["2024-10-31", "2024-11-30"]
    series = [f"s{i}" for i in range(21)]
    cells = []
    for origin in origins:
        for sid in series:
            for model in ("snaive7", "prophet_tuned"):
                failed = (origin, sid, model) == (origins[1], series[0], "prophet_tuned")
                cells.append(
                    {
                        "origin": origin,
                        "series_id": sid,
                        "model_id": model,
                        "status": "failed" if failed else "complete",
                        "n_actual": 28,
                        "n_predictions": 0 if failed else 28,
                        "metrics": None
                        if failed
                        else {
                            "n": 28,
                            "actual_sum": 100,
                            "abs_error_sum": 10 if model == "snaive7" else 20,
                        },
                    }
                )
    source = {
        "status": "partial_two_model_development_not_benchmark",
        "run_id": "development-two-model-123456789abc",
        "model_ids": ["snaive7", "prophet_tuned"],
        "origins": origins,
        "series_ids": series,
        "expected_cells": 84,
        "complete_cells": 83,
        "paired_two_model_cells": 41,
        "evaluation_cells": cells,
    }
    report = summarize(source)
    assert report["paired_series_origin_pairs"] == 41
    assert report["models"]["snaive7"]["paired_actual_sum"] == 4100
    assert report["models"]["snaive7"]["paired_pooled_wape"] == pytest.approx(0.1)
    assert report["models"]["prophet_tuned"]["paired_pooled_wape"] == pytest.approx(0.2)
    source["paired_two_model_cells"] = 42
    with pytest.raises(ValueError, match="paired"):
        summarize(source)
