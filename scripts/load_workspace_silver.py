"""Merge a verified development Silver snapshot into the workspace Delta table."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from databricks.sdk import WorkspaceClient
from verify_workspace_silver import SILVER, run_query

from nyc311_forecast.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--silver-dir", type=Path, default=SILVER)
    args = parser.parse_args()
    silver = args.silver_dir
    if args.output.exists():
        raise ValueError("Output evidence file already exists")
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
    manifest = json.loads((silver / "manifest.json").read_text(encoding="utf-8"))
    local_rows = [
        json.loads(line) for line in (silver / "daily_requests.jsonl").open(encoding="utf-8")
    ]
    last_date = max(row["ds"] for row in local_rows)
    client = WorkspaceClient(profile=config.workspace_profile)
    if client.config.host.rstrip("/") != config.workspace_host.rstrip("/"):
        raise ValueError("Authenticated workspace host differs from config")
    table = f"{config.catalog}.{config.schema}.daily_requests"
    volume_file = (
        f"/Volumes/{config.catalog}/{config.schema}/artifacts/"
        f"{manifest['snapshot_id']}/daily_requests.jsonl"
    )
    source = f"""SELECT snapshot_id, series_id, CAST(ds AS DATE) AS ds, borough,
  problem_family, y, is_zero_filled, quality_status, mapping_version
FROM read_files('{volume_file}', format => 'json',
  schema => 'snapshot_id STRING, series_id STRING, ds STRING, borough STRING, problem_family STRING, y BIGINT, is_zero_filled BOOLEAN, quality_status STRING, mapping_version STRING')"""
    snapshot_id = manifest["snapshot_id"]
    preflight_sql = f"""WITH source AS ({source})
SELECT COUNT(*), COUNT(DISTINCT concat_ws('|', snapshot_id, series_id, CAST(ds AS STRING))),
  SUM(y), SUM(CAST(is_zero_filled AS INT)),
  SUM(CASE WHEN snapshot_id = '{snapshot_id}' AND ds BETWEEN DATE '2021-01-01' AND DATE '{last_date}' THEN 0 ELSE 1 END)
FROM source"""
    preflight_id, preflight_data = run_query(
        client.statement_execution, config.warehouse_id, preflight_sql
    )
    rows, distinct_keys, requests, zero_filled, invalid = map(int, preflight_data[0])
    expected_requests = sum(row["y"] for row in local_rows)
    if (rows, distinct_keys, requests, zero_filled, invalid) != (
        manifest["row_count"],
        manifest["row_count"],
        expected_requests,
        manifest["zero_filled_rows"],
        0,
    ):
        raise ValueError("Source preflight failed; Delta merge was not attempted")
    merge_sql = f"""MERGE INTO {table} AS target
USING ({source}) AS source
ON target.snapshot_id = source.snapshot_id
 AND target.series_id = source.series_id AND target.ds = source.ds
WHEN NOT MATCHED THEN INSERT (
  snapshot_id, series_id, ds, borough, problem_family, y,
  is_zero_filled, quality_status, mapping_version
) VALUES (
  source.snapshot_id, source.series_id, source.ds, source.borough,
  source.problem_family, source.y, source.is_zero_filled,
  source.quality_status, source.mapping_version
)"""
    merge_id, _ = run_query(
        client.statement_execution, config.warehouse_id, merge_sql, timeout_seconds=600
    )
    check_sql = f"""WITH source AS ({source}), target AS (
  SELECT * FROM {table} WHERE snapshot_id = '{snapshot_id}'
), missing AS (
  SELECT s.snapshot_id, s.series_id, s.ds FROM source s
  LEFT ANTI JOIN target t ON s.snapshot_id=t.snapshot_id AND s.series_id=t.series_id AND s.ds=t.ds
), extra AS (
  SELECT t.snapshot_id, t.series_id, t.ds FROM target t
  LEFT ANTI JOIN source s ON s.snapshot_id=t.snapshot_id AND s.series_id=t.series_id AND s.ds=t.ds
), changed AS (
  SELECT s.snapshot_id, s.series_id, s.ds FROM source s JOIN target t
    ON s.snapshot_id=t.snapshot_id AND s.series_id=t.series_id AND s.ds=t.ds
  WHERE NOT (s.borough <=> t.borough AND s.problem_family <=> t.problem_family
    AND s.y <=> t.y AND s.is_zero_filled <=> t.is_zero_filled
    AND s.quality_status <=> t.quality_status AND s.mapping_version <=> t.mapping_version)
)
SELECT (SELECT COUNT(*) FROM target), (SELECT SUM(y) FROM target),
 (SELECT SUM(CAST(is_zero_filled AS INT)) FROM target),
 (SELECT COUNT(*) FROM missing), (SELECT COUNT(*) FROM extra),
 (SELECT COUNT(*) FROM changed)"""
    check_id, check_data = run_query(client.statement_execution, config.warehouse_id, check_sql)
    persisted_rows, persisted_requests, persisted_zero_filled, missing, extra, changed = map(
        int, check_data[0]
    )
    result = {
        "status": "verified"
        if (persisted_rows, persisted_requests, persisted_zero_filled, missing, extra, changed)
        == (rows, requests, zero_filled, 0, 0, 0)
        else "mismatch",
        "snapshot_id": snapshot_id,
        "payload_sha256": manifest["daily_payload_hash"],
        "table": table,
        "volume_file": volume_file,
        "preflight_query_id": preflight_id,
        "merge_query_id": merge_id,
        "postload_query_id": check_id,
        "source_rows": rows,
        "persisted_rows": persisted_rows,
        "persisted_requests": persisted_requests,
        "persisted_zero_filled": persisted_zero_filled,
        "missing_keys": missing,
        "extra_keys": extra,
        "changed_rows": changed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["status"] != "verified":
        raise ValueError("Persisted Delta rows failed source comparison")


if __name__ == "__main__":
    main()
