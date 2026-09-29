from datetime import date

import pytest

from nyc311_forecast.platform.native_sql import forecast_sql


def test_native_sql_bounds_version_and_escaping():
    sql = forecast_sql(catalog="main", schema="nyc311", snapshot_id="s'1", series_id="b/f", origin=date(2024, 12, 31))
    assert "DATE '2022-01-02'" in sql
    assert "DATE '2024-12-31'" in sql
    assert "horizon => '2025-01-29'" in sql
    assert "snapshot_id = 's''1'" in sql
    assert "positive_only => true" in sql
    assert "version => '2'" in sql
    assert "parameters =>" not in sql


def test_native_sql_rejects_identifier_injection():
    with pytest.raises(ValueError):
        forecast_sql(catalog="main;drop", schema="x", snapshot_id="s", series_id="s", origin=date(2024, 1, 31))
