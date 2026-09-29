from datetime import date, timedelta

from nyc311_forecast.evaluation.coverage import coverage_report


def test_missing_and_fallback_rows_remain_visible_in_pairing():
    origin = date(2024, 12, 31)
    rows = [
        {"model_id": model, "origin": origin, "series_id": "s", "ds": origin + timedelta(days=i), "prediction": 1.0}
        for model in ("snaive7", "ai_forecast_v2")
        for i in range(1, 29)
    ]
    rows.append({"model_id": "prophet_tuned", "origin": origin, "series_id": "s", "ds": origin + timedelta(days=1), "prediction": 1.0, "is_fallback": True})
    result = coverage_report(iter(["s"]), iter([origin]), iter(["snaive7", "prophet_tuned", "ai_forecast_v2"]), rows)
    assert result["paired_cells"] == 0
    assert result["per_model"]["prophet_tuned"] == {"expected": 1, "complete": 0}
    assert not result["unrestricted_comparison"]
    assert ("prophet_tuned", origin, "s") in result["invalid"]
