from pathlib import Path

from nyc311_forecast.platform.deploy import ddl_statements


def test_ddl_parser_ignores_comment_semicolons_and_keeps_all_tables():
    statements = ddl_statements(Path("sql/tables.sql"), catalog="mlops_dev", schema="nyc311_forecast")
    assert len(statements) == 10
    assert statements[0].startswith("CREATE TABLE IF NOT EXISTS mlops_dev.nyc311_forecast.source_partitions")
    assert statements[-1].startswith("CREATE TABLE IF NOT EXISTS mlops_dev.nyc311_forecast.release_claims")
