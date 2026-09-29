"""Synthetic fixtures only; these are contract checks, not benchmark results."""

from datetime import date, timedelta

import pytest

from nyc311_forecast.models.contracts import publish_prediction
from nyc311_forecast.models.prophet_adapter import ProphetParameters, tune_series
from nyc311_forecast.models.prophet_adapter import forecast as prophet_forecast
from nyc311_forecast.models.snaive import forecast as snaive_forecast

ORIGIN = date(2024, 12, 31)


def fixture():
    history = [{"ds": ORIGIN - timedelta(days=13 - i), "y": float(i % 7 + 1)} for i in range(14)]
    future = [ORIGIN + timedelta(days=i) for i in range(1, 29)]
    return history, future


def test_seven_day_calendar_parity_and_no_future_reads():
    history, future = fixture()
    result = snaive_forecast(history, future, series_id="bronx:heat", origin=ORIGIN)
    expected = [float(i) for i in range(1, 8)] * 4
    assert [row.prediction for row in result.predictions] == expected
    assert [row.ds for row in result.predictions] == future
    assert all(row.lower is None and row.upper is None for row in result.predictions)
    assert result.lineage["training_last_date"] == ORIGIN.isoformat()


@pytest.mark.parametrize(
    "change",
    [
        lambda rows: rows + [{"ds": ORIGIN + timedelta(days=1), "y": 999.0}],
        lambda rows: rows[:-1],
        lambda rows: rows[:3] + rows[4:],
        lambda rows: rows[:5] + [rows[4]] + rows[5:],
    ],
)
def test_history_leakage_missing_day_and_duplicate_rejected(change):
    history, future = fixture()
    with pytest.raises(ValueError):
        snaive_forecast(change(history), future, series_id="x", origin=ORIGIN)


def test_future_grid_must_be_full_28_calendar_days():
    history, future = fixture()
    with pytest.raises(ValueError):
        snaive_forecast(history, future[:7], series_id="x", origin=ORIGIN)
    with pytest.raises(ValueError):
        snaive_forecast(
            history, future[:6] + [future[7]] + future[7:], series_id="x", origin=ORIGIN
        )


def test_nonnegative_publication_retains_raw_values():
    row = publish_prediction(
        ORIGIN + timedelta(days=1), 1, -2.5, raw_lower=-7.0, raw_upper=1.2, interval_level=0.8
    )
    assert (row.prediction, row.lower, row.upper) == (0.0, 0.0, 1.2)
    assert (row.raw_prediction, row.raw_lower, row.raw_upper) == (-2.5, -7.0, 1.2)
    assert row.transformed
    with pytest.raises(ValueError):
        publish_prediction(row.ds, 1, 1.0, raw_lower=2.0, raw_upper=1.0, interval_level=0.8)


def test_prophet_adapter_uses_same_bounded_history_and_normalizes(monkeypatch):
    history, future = fixture()
    seen = {}

    def fake_fit(rows, dates, parameters):
        seen["last_date"] = rows[-1].ds
        seen["dates"] = dates
        seen["parameters"] = parameters
        return ((-1.0, -2.0, 3.0),) * 28

    monkeypatch.setattr("nyc311_forecast.models.prophet_adapter._fit_predict", fake_fit)
    parameters = ProphetParameters(0.05, 2.0, "additive")
    result = prophet_forecast(
        history, future, series_id="x", origin=ORIGIN, model_config=parameters
    )
    assert seen == {"last_date": ORIGIN, "dates": tuple(future), "parameters": parameters}
    assert len(result.predictions) == 28
    assert result.predictions[0].prediction == 0.0
    assert result.predictions[0].raw_prediction == -1.0
    assert result.predictions[0].interval_level == 0.8


def test_model_rejects_history_longer_than_protocol_window():
    future = [ORIGIN + timedelta(days=i) for i in range(1, 29)]
    history = [{"ds": ORIGIN - timedelta(days=1095 - i), "y": 1.0} for i in range(1096)]
    with pytest.raises(ValueError, match="1,095"):
        snaive_forecast(history, future, series_id="x", origin=ORIGIN)


def test_tuning_uses_only_three_bounded_inner_windows(monkeypatch):
    pytest.importorskip("optuna")
    start = date(2021, 1, 1)
    end = date(2024, 10, 28)
    history = [{"ds": start + timedelta(days=i), "y": 10.0} for i in range((end - start).days + 1)]
    seen = []

    def fake_fit(rows, dates, parameters):
        seen.append((rows[0].ds, rows[-1].ds, dates[0], dates[-1], len(rows)))
        return ((10.0, 8.0, 12.0),) * 28

    monkeypatch.setattr("nyc311_forecast.models.prophet_adapter._fit_predict", fake_fit)
    result = tune_series(history, series_id="x", n_trials=1)
    assert result.pooled_wape == 0.0
    assert len(result.trials) == 1
    assert [window[1] for window in seen] == [
        date(2024, 1, 31),
        date(2024, 5, 31),
        date(2024, 9, 30),
    ]
    assert all(
        first == cutoff - timedelta(days=1094) and length == 1095
        for first, cutoff, _, _, length in seen
    )
    assert all(
        first == cutoff + timedelta(days=1) and last == cutoff + timedelta(days=28)
        for _, cutoff, first, last, _ in seen
    )


def test_tuning_refuses_evaluation_year_even_if_inner_windows_exist():
    pytest.importorskip("optuna")
    start = date(2021, 1, 1)
    history = [
        {"ds": start + timedelta(days=i), "y": 10.0}
        for i in range((date(2025, 1, 1) - start).days + 1)
    ]
    with pytest.raises(ValueError, match="2025"):
        tune_series(history, series_id="x", n_trials=1)


def test_real_prophet_predicts_28_calendar_days():
    pytest.importorskip("prophet")
    origin = date(2024, 12, 31)
    history = [{"ds": origin - timedelta(days=89 - i), "y": float(20 + i % 7)} for i in range(90)]
    future = [origin + timedelta(days=i) for i in range(1, 29)]
    result = prophet_forecast(
        history,
        future,
        series_id="synthetic",
        origin=origin,
        model_config=ProphetParameters(0.05, 1.0, "additive"),
    )
    assert [row.ds for row in result.predictions] == future
    assert all(row.lower <= row.upper for row in result.predictions)
    assert all(row.prediction >= 0 for row in result.predictions)
