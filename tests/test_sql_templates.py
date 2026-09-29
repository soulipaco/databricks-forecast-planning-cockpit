from pathlib import Path

import pytest

from nyc311_forecast.platform.sql_templates import render_sql


def test_contract_tables_render_only_safe_identifiers():
    sql = render_sql(Path("sql/tables.sql"), catalog="main", schema="nyc311")
    assert "main.nyc311.forecast_values" in sql
    assert sql.count("CREATE TABLE IF NOT EXISTS") == 10
    with pytest.raises(ValueError):
        render_sql(Path("sql/tables.sql"), catalog="main;drop", schema="nyc311")
