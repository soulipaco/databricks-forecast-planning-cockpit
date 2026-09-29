from datetime import date, timedelta
from types import SimpleNamespace

from nyc311_forecast.development_slice import run_slice
from nyc311_forecast.models.contracts import ForecastResult, publish_prediction


def test_development_slice_keeps_failed_cell_and_paired_denominator():
    series_id = "BRONX|Illegal Parking"
    start = date(2021, 1, 1)
    rows = [
        {"ds": start + timedelta(days=day), "y": 10 + day % 7}
        for day in range((date(2024, 12, 29) - start).days)
    ]

    def baseline(history, dates, *, series_id, origin, model_config, execution_context):
        assert len(history) == 1095
        assert history[-1]["ds"] == origin
        return ForecastResult(
            "snaive7",
            series_id,
            origin,
            tuple(publish_prediction(day, lead, 10.0) for lead, day in enumerate(dates, 1)),
        )

    def prophet(history, dates, *, series_id, origin, model_config, execution_context):
        if origin == date(2024, 11, 30):
            raise RuntimeError("fit failed")
        return ForecastResult(
            "prophet_tuned",
            series_id,
            origin,
            tuple(
                publish_prediction(
                    day, lead, 11.0, raw_lower=9.0, raw_upper=13.0, interval_level=0.8
                )
                for lead, day in enumerate(dates, 1)
            ),
        )

    result = run_slice(
        (series_id,),
        {series_id: rows},
        {
            "snaive7": (SimpleNamespace(forecast=baseline), None),
            "prophet_fixed_smoke": (SimpleNamespace(forecast=prophet), None),
        },
    )
    assert result["expected_cells"] == 4
    assert result["complete_cells"] == 3
    assert result["paired_local_cells"] == 1
    assert len(result["attempts"]) == 4
    assert len(result["forecast_values"]) == 84
    assert result["attempts"][-1]["error_class"] == "RuntimeError"
    assert result["attempts"][-1]["safe_error_message"] == "fit failed"
