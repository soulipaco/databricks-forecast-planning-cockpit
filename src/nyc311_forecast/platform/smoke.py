"""Bounded workspace capability check for explicitly pinned ai_forecast v2."""

from __future__ import annotations

from datetime import date
from time import monotonic, sleep

from nyc311_forecast.models.contracts import ForecastResult
from nyc311_forecast.platform.native_sql import normalize_native_rows

SMOKE_SQL = """WITH dates AS (
  SELECT explode(sequence(DATE '2024-01-01', DATE '2024-12-31', INTERVAL 1 DAY)) AS ds
), observed AS (
  SELECT ds, CAST(100 + 10 * dayofweek(ds) AS DOUBLE) AS y FROM dates
)
SELECT * FROM ai_forecast(
  TABLE(observed),
  horizon => '2025-01-29',
  time_col => 'ds',
  value_col => 'y',
  frequency => 'D',
  prediction_interval_width => 0.8,
  positive_only => true,
  version => '2'
)"""


def run_v2_smoke(api, warehouse_id: str, *, timeout_seconds: int = 600) -> ForecastResult:
    """Run one synthetic SQL query and validate all 28 returned rows."""
    from databricks.sdk.service.sql import ExecuteStatementRequestOnWaitTimeout, StatementState

    if not warehouse_id:
        raise ValueError("warehouse_id is required")
    started = monotonic()
    response = api.execute_statement(
        statement=SMOKE_SQL,
        warehouse_id=warehouse_id,
        wait_timeout="50s",
        on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CONTINUE,
        row_limit=28,
    )
    statement_id = response.statement_id
    if not statement_id:
        raise RuntimeError("Smoke statement returned no query ID")
    while response.status and response.status.state in (StatementState.PENDING, StatementState.RUNNING):
        if monotonic() - started >= timeout_seconds:
            raise TimeoutError(f"v2 smoke exceeded {timeout_seconds}s; query ID {statement_id}")
        sleep(2)
        response = api.get_statement(statement_id)
    if not response.status or response.status.state != StatementState.SUCCEEDED:
        state = response.status.state if response.status else "missing status"
        raise RuntimeError(f"v2 smoke failed with state {state}; query ID {statement_id}")
    if not response.manifest or response.manifest.truncated:
        raise ValueError("Smoke result manifest absent or truncated")
    columns = response.manifest.schema.columns if response.manifest.schema else None
    if not columns or not response.result or not response.result.data_array:
        raise ValueError("Smoke returned no result rows or columns")
    names = [column.name for column in columns]
    if set(names) != {"ds", "y_forecast", "y_lower", "y_upper"}:
        raise ValueError(f"Unexpected v2 output columns: {names}")
    rows = [dict(zip(names, values)) for values in response.result.data_array]
    for row in rows:
        for field in ("y_forecast", "y_lower", "y_upper"):
            row[field] = float(row[field])
    return normalize_native_rows(
        rows, series_id="synthetic-smoke", origin=date(2024, 12, 31),
        query_id=statement_id, wall_seconds=monotonic() - started,
    )
