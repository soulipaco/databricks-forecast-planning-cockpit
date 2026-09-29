from pathlib import Path

from nyc311_forecast.platform.deploy import ddl_statements, view_statements


def test_ddl_parser_ignores_comment_semicolons_and_keeps_all_tables():
    statements = ddl_statements(
        Path("sql/tables.sql"), catalog="mlops_dev", schema="nyc311_forecast"
    )
    assert len(statements) == 10
    assert statements[0].startswith(
        "CREATE TABLE IF NOT EXISTS mlops_dev.nyc311_forecast.source_partitions"
    )
    assert statements[-1].startswith(
        "CREATE TABLE IF NOT EXISTS mlops_dev.nyc311_forecast.release_claims"
    )


def test_view_parser_keeps_five_materialized_data_views():
    statements = view_statements(
        Path("sql/views.sql"), catalog="mlops_dev", schema="nyc311_forecast"
    )
    assert len(statements) == 5
    assert statements[0].startswith(
        "CREATE OR REPLACE VIEW mlops_dev.nyc311_forecast.v_forecast_detail"
    )
    assert statements[-1].startswith(
        "CREATE OR REPLACE VIEW mlops_dev.nyc311_forecast.v_data_quality"
    )
    assert all("ai_forecast(" not in statement for statement in statements)
