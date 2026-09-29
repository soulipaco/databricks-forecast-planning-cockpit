"""ai_forecast v2 on the 2024 development grid, scored exactly like the two-model run.

Inference runs in a Databricks SQL warehouse over the verified Delta Silver table; actuals
and the MASE scale come from the same committed local Silver payload. No 2025 data enters.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep
from typing import Any

from nyc311_forecast.config import load_config
from nyc311_forecast.contracts import assert_unique, validate_forecast
from nyc311_forecast.development_compare import ROOT, load_inputs
from nyc311_forecast.evaluation.metrics import score
from nyc311_forecast.evaluation.splits import DEVELOPMENT_ORIGINS, bounded_history, future_dates
from nyc311_forecast.platform.native_sql import forecast_sql, normalize_native_rows

MODEL_ID = "ai_forecast_v2"
STATUS = "native_v2_development_not_benchmark"
TRANSIENT_CODES = {"TEMPORARILY_UNAVAILABLE", "RESOURCE_EXHAUSTED", "DEADLINE_EXCEEDED"}


class TransientNativeError(RuntimeError):
    """A warehouse failure that the protocol allows retrying with identical inputs."""


Executor = Callable[[str], tuple[str, list[dict], float]]


def run_native(
    series_ids: tuple[str, ...],
    by_series: Mapping[str, list[dict]],
    execute: Executor,
    *,
    catalog: str,
    schema: str,
    snapshot_id: str,
    run_tag: str,
    max_retries: int = 2,
    retry_wait_seconds: float = 10.0,
) -> dict:
    """Keep every expected cell and attempt; retry only transient warehouse failures."""
    if not series_ids or len(set(series_ids)) != len(series_ids):
        raise ValueError("series_ids must be nonempty and unique")
    attempts, values, cells = [], [], []
    for origin in DEVELOPMENT_ORIGINS:
        dates = future_dates(origin)
        for series_id in series_ids:
            rows = by_series.get(series_id, [])
            key = {"origin": origin.isoformat(), "series_id": series_id, "model_id": MODEL_ID}
            cell = {**key, "horizon_days": 28, "n_expected": 28, "n_actual": 0,
                    "n_predictions": 0, "status": "failed"}
            try:
                history = bounded_history(rows, origin)
                actual_by_date = {row["ds"]: row["y"] for row in rows if row["ds"] in dates}
                if len(actual_by_date) != 28:
                    raise ValueError("Actual validation grid has missing or duplicate dates")
                actual = [actual_by_date[ds] for ds in dates]
                cell["n_actual"] = 28
                # The unique comment defeats the SQL result cache; cache use is verified later.
                sql = (
                    f"/* nyc311 {run_tag} {series_id} {origin.isoformat()} */\n"
                    + forecast_sql(catalog=catalog, schema=schema, snapshot_id=snapshot_id,
                                   series_id=series_id, origin=origin)
                )
            except Exception as exc:  # noqa: BLE001 - input failures stay visible in the grid
                attempts.append({**key, "attempt_no": 1, "status": "failed",
                                 "error_class": type(exc).__name__,
                                 "safe_error_message": str(exc)[:240]})
                cells.append({**cell, "error_class": type(exc).__name__})
                continue
            for attempt_no in range(1, max_retries + 2):
                attempt = {**key, "attempt_no": attempt_no, "status": "failed"}
                try:
                    query_id, raw_rows, wall_seconds = execute(sql)
                    attempt.update(query_id=query_id, wall_seconds=wall_seconds)
                    result = normalize_native_rows(raw_rows, series_id=series_id, origin=origin,
                                                   query_id=query_id, wall_seconds=wall_seconds)
                    validate_forecast(
                        ({"ds": p.ds, "prediction": p.prediction, "lower": p.lower,
                          "upper": p.upper} for p in result.predictions),
                        origin,
                    )
                    lower = [p.lower for p in result.predictions]
                    upper = [p.upper for p in result.predictions]
                    if any(lo is None or hi is None for lo, hi in zip(lower, upper)):
                        raise ValueError("Native interval grid is incomplete")
                    metrics = score(actual, [p.prediction for p in result.predictions],
                                    [row["y"] for row in history], lower, upper)
                except TransientNativeError as exc:
                    attempt.update(error_class=type(exc).__name__,
                                   safe_error_message=str(exc)[:240])
                    attempts.append(attempt)
                    if attempt_no <= max_retries:
                        sleep(retry_wait_seconds)
                        continue
                    cell["error_class"] = type(exc).__name__
                    break
                except Exception as exc:  # noqa: BLE001 - data/contract errors are not retried
                    attempt.update(error_class=type(exc).__name__,
                                   safe_error_message=str(exc)[:240])
                    attempts.append(attempt)
                    cell["error_class"] = type(exc).__name__
                    break
                attempt["status"] = "success"
                attempts.append(attempt)
                cell.update(status="complete", n_predictions=28, query_id=query_id,
                            metrics=asdict(metrics))
                values.extend(
                    {**key, "ds": p.ds.isoformat(), "lead_day": p.lead_day,
                     "actual": actual_by_date[p.ds], "prediction": p.prediction,
                     "raw_prediction": p.raw_prediction, "lower": p.lower, "upper": p.upper,
                     "raw_lower": p.raw_lower, "raw_upper": p.raw_upper,
                     "interval_level": p.interval_level, "transformed": p.transformed,
                     "is_fallback": p.is_fallback}
                    for p in result.predictions
                )
                break
            cells.append(cell)
    expected = len(series_ids) * len(DEVELOPMENT_ORIGINS)
    if len(cells) != expected:
        raise AssertionError("Expected series/origin grid was lost")
    assert_unique("forecast_values", ({"run_id": "native", **row} for row in values))
    complete = sum(cell["status"] == "complete" for cell in cells)
    return {
        "status": STATUS,
        "model_ids": [MODEL_ID],
        "origins": [origin.isoformat() for origin in DEVELOPMENT_ORIGINS],
        "series_ids": list(series_ids),
        "expected_cells": expected,
        "complete_cells": complete,
        "failed_cells": expected - complete,
        "attempts": attempts,
        "evaluation_cells": cells,
        "forecast_values": values,
    }


def warehouse_executor(client, warehouse_id: str, *, timeout_seconds: int) -> Executor:
    from databricks.sdk.service.sql import ExecuteStatementRequestOnWaitTimeout, StatementState

    def execute(sql: str) -> tuple[str, list[dict], float]:
        started = monotonic()
        try:
            response = client.statement_execution.execute_statement(
                statement=sql, warehouse_id=warehouse_id, wait_timeout="50s",
                on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CONTINUE,
            )
        except (ConnectionError, TimeoutError) as exc:
            raise TransientNativeError(str(exc)) from exc
        query_id = response.statement_id
        while response.status and response.status.state in (
            StatementState.PENDING, StatementState.RUNNING
        ):
            if monotonic() - started >= timeout_seconds:
                client.statement_execution.cancel_execution(query_id)
                raise TransientNativeError(f"query {query_id} exceeded {timeout_seconds}s")
            sleep(2)
            response = client.statement_execution.get_statement(query_id)
        state = response.status.state if response.status else None
        if state != StatementState.SUCCEEDED:
            error = response.status.error if response.status else None
            code = str(error.error_code.value if error and error.error_code else "unknown")
            message = (error.message or "") if error else ""
            text = f"query {query_id} {state}: {code}: {message.splitlines()[-1] if message else ''}"
            if code in TRANSIENT_CODES:
                raise TransientNativeError(text)
            raise RuntimeError(text)
        if not response.manifest or response.manifest.truncated or not response.result:
            raise ValueError(f"query {query_id} returned no complete result")
        names = [column.name for column in response.manifest.schema.columns]
        rows = [dict(zip(names, values)) for values in response.result.data_array or []]
        for row in rows:
            for field in ("y_forecast", "y_lower", "y_upper"):
                row[field] = float(row[field])
        return query_id, rows, monotonic() - started

    return execute


def query_metrics(client, query_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Read execution metadata so cached results cannot pass as inference."""
    from databricks.sdk.service.sql import QueryFilter

    found: dict[str, dict[str, Any]] = {}
    for start in range(0, len(query_ids), 50):
        chunk = query_ids[start:start + 50]
        response = client.query_history.list(
            filter_by=QueryFilter(statement_ids=chunk), include_metrics=True, max_results=50
        )
        for query in response.res or []:
            metrics = query.metrics
            found[query.query_id] = {
                "result_from_cache": getattr(metrics, "result_from_cache", None),
                "execution_time_ms": getattr(metrics, "execution_time_ms", None),
                "total_time_ms": getattr(metrics, "total_time_ms", None),
                "compilation_time_ms": getattr(metrics, "compilation_time_ms", None),
            }
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--series-limit", type=int, default=None)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output already exists; choose a new evidence path")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        raise RuntimeError("Commit code and inputs before a traceable run")
    code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    config = load_config(args.config)
    if not all((config.workspace_profile, config.warehouse_id, config.catalog, config.schema)):
        raise ValueError("workspace_profile, warehouse_id, catalog and schema are required")
    from databricks.sdk import WorkspaceClient

    client = WorkspaceClient(profile=config.workspace_profile)
    if config.workspace_host and client.config.host.rstrip("/") != config.workspace_host.rstrip("/"):
        raise ValueError("Authenticated workspace host differs from config")
    series_ids, by_series, _parameters, provenance = load_inputs()
    if args.series_limit:
        series_ids = series_ids[: args.series_limit]
    run_id = f"development-native-v2-{code_sha[:12]}"
    started = datetime.now(UTC)
    output = run_native(
        series_ids, by_series,
        warehouse_executor(client, config.warehouse_id,
                           timeout_seconds=config.task_timeout_seconds),
        catalog=config.catalog, schema=config.schema,
        snapshot_id=provenance["silver_snapshot_id"], run_tag=run_id,
        max_retries=config.max_retries,
    )
    query_ids = [a["query_id"] for a in output["attempts"] if a.get("query_id")]
    sleep(20)  # query history is eventually consistent
    metadata = query_metrics(client, query_ids)
    for attempt in output["attempts"]:
        if attempt.get("query_id"):
            attempt["query_metrics"] = metadata.get(attempt["query_id"])
    output.update(provenance)
    output.update({
        "run_id": run_id,
        "code_sha": code_sha,
        "started_at_utc": started.isoformat(),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "workspace": "non-Free-Edition trial workspace; host kept out of public evidence",
        "delta_table": f"{config.catalog}.{config.schema}.daily_requests",
        "series_limit": args.series_limit,
        "queries_with_metrics": sum(1 for q in query_ids if q in metadata),
        "queries_from_cache": sum(
            1 for q in query_ids if (metadata.get(q) or {}).get("result_from_cache")
        ),
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(output, stream, indent=2, sort_keys=True, allow_nan=False, default=str)
        stream.write("\n")
    print(json.dumps({k: output[k] for k in (
        "run_id", "expected_cells", "complete_cells", "failed_cells",
        "queries_with_metrics", "queries_from_cache")} | {"output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
