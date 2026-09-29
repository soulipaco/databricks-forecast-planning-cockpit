"""Pinned ai_forecast v2 SQL for one validated series and origin.

The SQL reads exactly one immutable snapshot and the last 1,095 civil dates.
Execution and result publication must be supplied by a workspace adapter.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import date, timedelta

from nyc311_forecast.models.contracts import ForecastResult, publish_prediction

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


def normalize_native_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    series_id: str,
    origin: date,
    query_id: str | None = None,
    wall_seconds: float | None = None,
) -> ForecastResult:
    """Validate observed v2 result columns; never fill absent forecasts."""
    parsed = []
    for row in rows:
        day = row["ds"]
        if isinstance(day, str):
            day = date.fromisoformat(day)
        if not isinstance(day, date):
            raise TypeError("Native forecast date must be a civil date")
        lead = (day - origin).days
        parsed.append(
            publish_prediction(
                day, lead, row["y_forecast"], raw_lower=row["y_lower"],
                raw_upper=row["y_upper"], interval_level=0.8,
            )
        )
    return ForecastResult(
        model_id="ai_forecast_v2", series_id=series_id, origin=origin,
        predictions=tuple(sorted(parsed, key=lambda value: value.ds)),
        wall_seconds=wall_seconds, lineage={"query_id": query_id, "version": "2"},
    )
