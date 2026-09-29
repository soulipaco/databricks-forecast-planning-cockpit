"""Compare the uploaded development Silver file with the local manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import monotonic, sleep

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import ExecuteStatementRequestOnWaitTimeout, StatementState

from nyc311_forecast.config import load_config

ROOT = Path(__file__).resolve().parents[1]
SILVER = ROOT / "data/silver/development-silver-20260929"


def run_query(api, warehouse_id: str, sql: str, *, timeout_seconds: int = 180):
    start = monotonic()
    response = api.execute_statement(
        statement=sql,
        warehouse_id=warehouse_id,
        wait_timeout="30s",
        on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CONTINUE,
    )
    query_id = response.statement_id
    while response.status and response.status.state in (
        StatementState.PENDING,
        StatementState.RUNNING,
    ):
        if monotonic() - start > timeout_seconds:
            raise TimeoutError(f"SQL query timed out; query ID {query_id}")
        sleep(2)
        response = api.get_statement(query_id)
    if not response.status or response.status.state != StatementState.SUCCEEDED:
        error = response.status.error if response.status else None
        message = error.message.splitlines()[0] if error and error.message else "unknown"
        raise RuntimeError(f"SQL query failed: {message}; query ID {query_id}")
    return query_id, response.result.data_array if response.result else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    if not all(
        (
            config.workspace_host,
            config.workspace_profile,
            config.warehouse_id,
            config.catalog,
            config.schema,
        )
    ):
        raise ValueError("Workspace host, profile, warehouse, catalog and schema are required")
    local = json.loads((SILVER / "manifest.json").read_text(encoding="utf-8"))
    client = WorkspaceClient(profile=config.workspace_profile)
    if client.config.host.rstrip("/") != config.workspace_host.rstrip("/"):
        raise ValueError("Authenticated workspace host differs from config")
    path = f"/Volumes/{config.catalog}/{config.schema}/artifacts/{local['snapshot_id']}/daily_requests.jsonl"
    sql = f"""SELECT COUNT(*) AS rows, SUM(y) AS requests,
  SUM(CAST(is_zero_filled AS INT)) AS zero_filled
FROM read_files('{path}', format => 'json',
  schema => 'snapshot_id STRING, series_id STRING, ds STRING, borough STRING, problem_family STRING, y BIGINT, is_zero_filled BOOLEAN, quality_status STRING, mapping_version STRING')"""
    query_id, data = run_query(client.statement_execution, config.warehouse_id, sql)
    if not data or len(data) != 1:
        raise ValueError("Unexpected workspace aggregate result")
    rows, requests, zero_filled = map(int, data[0])
    expected_requests = sum(
        json.loads(line)["y"] for line in (SILVER / "daily_requests.jsonl").open(encoding="utf-8")
    )
    if (rows, requests, zero_filled) != (
        local["row_count"],
        expected_requests,
        local["zero_filled_rows"],
    ):
        raise ValueError("Workspace file does not match local Silver counts")
    print(
        json.dumps(
            {
                "status": "verified",
                "query_id": query_id,
                "snapshot_id": local["snapshot_id"],
                "rows": rows,
                "requests": requests,
                "zero_filled": zero_filled,
                "local_payload_hash": local["daily_payload_hash"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
