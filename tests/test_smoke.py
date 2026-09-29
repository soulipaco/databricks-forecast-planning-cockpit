from datetime import date, timedelta
from types import SimpleNamespace

from databricks.sdk.service.sql import StatementState

from nyc311_forecast.platform.smoke import run_v2_smoke


def test_v2_smoke_checks_query_and_28_rows_without_workspace():
    origin = date(2024, 12, 31)
    data = [
        [(origin + timedelta(days=i)).isoformat(), "10.0", "8.0", "12.0"]
        for i in range(1, 29)
    ]
    response = SimpleNamespace(
        statement_id="query-1",
        status=SimpleNamespace(state=StatementState.SUCCEEDED),
        manifest=SimpleNamespace(
            truncated=False,
            schema=SimpleNamespace(columns=[SimpleNamespace(name=n) for n in ("ds", "y_forecast", "y_lower", "y_upper")]),
        ),
        result=SimpleNamespace(data_array=data),
    )

    class FakeAPI:
        def execute_statement(self, **kwargs):
            assert "version => '2'" in kwargs["statement"]
            assert kwargs["warehouse_id"] == "warehouse"
            return response

    result = run_v2_smoke(FakeAPI(), "warehouse")
    assert len(result.predictions) == 28
    assert result.lineage["query_id"] == "query-1"
