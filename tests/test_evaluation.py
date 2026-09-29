from datetime import date, timedelta

import pytest

from nyc311_forecast.evaluation.metrics import pooled_wape, score
from nyc311_forecast.evaluation.splits import FINAL_ORIGINS, bounded_history, future_dates


def test_history_is_bounded_and_rejects_training_gap():
    origin = date(2024, 12, 31)
    first = origin - timedelta(days=1094)
    rows = [{"ds": first + timedelta(days=i), "y": 10} for i in range(1095)]
    rows += [{"ds": origin + timedelta(days=1), "y": 999}]
    assert max(r["ds"] for r in bounded_history(rows, origin)) == origin
    with pytest.raises(ValueError):
        bounded_history(rows[1:], origin)


def test_final_origins_and_28_day_horizon():
    assert len(FINAL_ORIGINS) == 12
    assert FINAL_ORIGINS[0] == date(2024, 12, 31)
    assert FINAL_ORIGINS[-1] == date(2025, 11, 30)
    assert future_dates(FINAL_ORIGINS[-1])[-1] == date(2025, 12, 28)


def test_metric_arithmetic_and_ratio_of_sums():
    train = list(range(1095))
    a = score([10, 20], [12, 18], train, [8, 15], [11, 19])
    b = score([1], [2], train)
    assert a.abs_error_sum == 4
    assert a.signed_error_sum == 0
    assert a.wape == pytest.approx(4 / 30)
    assert a.interval_hits == 1
    assert a.interval_score_sum == pytest.approx(3 + 4 + 10)
    assert pooled_wape([a, b]) == pytest.approx(5 / 31)
    assert b.interval_n == 0


def test_zero_denominators_are_unavailable():
    result = score([0], [0], [5] * 1095)
    assert result.wape is None
    assert result.mase is None


def test_nonfinite_prediction_is_rejected():
    with pytest.raises(ValueError, match="Non-finite"):
        score([1], [float("nan")], [5] * 1095)
