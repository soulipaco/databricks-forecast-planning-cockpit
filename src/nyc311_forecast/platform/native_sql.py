"""Pinned ai_forecast v2 SQL for one validated series and origin.

The SQL reads exactly one immutable snapshot and the last 1,095 civil dates.
Execution and result publication must be supplied by a workspace adapter.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def forecast_sql(*, catalog: str, schema: str, snapshot_id: str, series_id: str, origin: date) -> str:
    for value in (catalog, schema):
        if not IDENTIFIER.fullmatch(value):
            raise ValueError("Unsafe SQL identifier")
    if not snapshot_id or not series_id:
        raise ValueError("Snapshot and series are required")
    # Databricks SQL string literals escape a single quote by doubling it.
    snap = snapshot_id.replace("'", "''")
    series = series_id.replace("'", "''")
    first = origin - timedelta(days=1094)
    end = origin + timedelta(days=29)  # right-exclusive, 28 result dates
    return f"""WITH observed AS (
  SELECT ds, CAST(y AS DOUBLE) AS y
  FROM {catalog}.{schema}.daily_requests
  WHERE snapshot_id = '{snap}'
    AND series_id = '{series}'
    AND ds BETWEEN DATE '{first.isoformat()}' AND DATE '{origin.isoformat()}'
    AND quality_status = 'complete'
)
SELECT ds, y_forecast, y_lower, y_upper
FROM ai_forecast(
  TABLE(observed),
  horizon => '{end.isoformat()}',
  time_col => 'ds',
  value_col => 'y',
  frequency => 'D',
  prediction_interval_width => 0.8,
  positive_only => true,
  version => '2'
)"""
