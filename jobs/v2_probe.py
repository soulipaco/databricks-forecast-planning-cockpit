"""Diagnostic job: run the pinned ai_forecast v2 smoke through serverless job compute.

Same SQL as the warehouse smoke; only the execution surface differs. Validates 28 dates.
"""

import json
import time

from pyspark.sql import SparkSession

from nyc311_forecast.platform.smoke import SMOKE_SQL

if __name__ == "__main__":
    spark = SparkSession.builder.getOrCreate()
    started = time.monotonic()
    rows = [r.asDict() for r in spark.sql(SMOKE_SQL).collect()]
    report = {
        "surface": "serverless_job_spark_sql",
        "wall_seconds": round(time.monotonic() - started, 1),
        "rows": len(rows),
        "columns": sorted(rows[0]) if rows else [],
        "first_ds": str(min(r["ds"] for r in rows)) if rows else None,
        "last_ds": str(max(r["ds"] for r in rows)) if rows else None,
        "interval_ordered": all(r["y_lower"] <= r["y_forecast"] <= r["y_upper"] for r in rows),
    }
    print(json.dumps(report, indent=2))
    if report["rows"] != 28 or not report["interval_ordered"]:
        raise SystemExit(1)
