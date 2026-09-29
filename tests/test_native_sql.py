from datetime import date, timedelta

import pytest

from nyc311_forecast.platform.native_sql import forecast_sql, normalize_native_rows


def test_native_sql_bounds_version_and_escaping():
    sql = forecast_sql(catalog="main", schema="nyc311", snapshot_id="s'1", series_id="b/f", origin=date(2024, 12, 31))
    assert "DATE '2022-01-02'" in sql
    assert "DATE '2024-12-31'" in sql
    assert "horizon => '2025-01-28'" in sql
    assert "snapshot_id = 's''1'" in sql
    assert "positive_only => true" in sql
    assert "version => '2'" in sql
    assert "parameters =>" not in sql


def test_native_sql_rejects_identifier_injection():
    with pytest.raises(ValueError):
        forecast_sql(catalog="main;drop", schema="x", snapshot_id="s", series_id="s", origin=date(2024, 1, 31))


def test_native_result_requires_full_grid_and_keeps_query_lineage():
    origin = date(2024, 12, 31)
    rows = [
        {"ds": origin + timedelta(days=i), "y_forecast": 2.0, "y_lower": 1.0, "y_upper": 3.0}
        for i in range(1, 29)
    ]
    result = normalize_native_rows(rows, series_id="BRONX|A", origin=origin, query_id="q")
    assert result.lineage["query_id"] == "q"
    assert len(result.predictions) == 28
    with pytest.raises(ValueError):
        normalize_native_rows(rows[:-1], series_id="BRONX|A", origin=origin)
    extra = {"ds": origin + timedelta(days=29), "y_forecast": 2.0, "y_lower": 1.0, "y_upper": 3.0}
    with pytest.raises(ValueError):  # an inclusive-horizon 29th row must not pass silently
        normalize_native_rows([*rows, extra], series_id="BRONX|A", origin=origin)
