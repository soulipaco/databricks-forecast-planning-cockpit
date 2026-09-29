from datetime import date, timedelta

import pytest

from nyc311_forecast.config import Config
from nyc311_forecast.contracts import assert_unique, validate_forecast


def test_duplicate_vintage_is_rejected_but_distinct_origins_are_allowed():
    row = {"run_id": "r", "model_id": "m", "origin": date(2024, 1, 1), "series_id": "s", "ds": date(2024, 1, 2)}
    assert_unique("forecast_values", [row, {**row, "origin": date(2024, 1, 2)}])
    with pytest.raises(ValueError, match="Duplicate"):
        assert_unique("forecast_values", [row, row])


def test_forecast_grid_rejects_duplicate_even_when_count_is_28():
    origin = date(2024, 1, 31)
    rows = [{"ds": origin + timedelta(days=i), "prediction": 1.0} for i in range(1, 29)]
    assert len(validate_forecast(rows, origin)) == 28
    rows[-1]["ds"] = rows[-2]["ds"]
    with pytest.raises(ValueError):
        validate_forecast(rows, origin)


def test_sql_identifier_rejects_injection():
    with pytest.raises(ValueError, match="identifier"):
        Config("e", "s", catalog="main; DROP TABLE x")
