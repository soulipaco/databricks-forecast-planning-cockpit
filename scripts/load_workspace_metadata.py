"""Idempotently merge staged source and selection lineage into Delta."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from databricks.sdk import WorkspaceClient
from verify_workspace_silver import ROOT, run_query

from nyc311_forecast.config import load_config

STAGE = ROOT / "data/workspace_stage/development-metadata-20260929"
TABLES = {
    "source_partitions": {
        "fields": (
            "snapshot_id",
            "partition_id",
            "endpoint",
            "query_hash",
            "extracted_at",
            "payload_hash",
            "aggregate_rows",
            "source_count",
            "grouped_count",
            "status",
        ),
        "keys": ("snapshot_id", "partition_id"),
        "schema": (
            "snapshot_id STRING, partition_id STRING, endpoint STRING, query_hash STRING, "
            "extracted_at STRING, payload_hash STRING, aggregate_rows BIGINT, "
            "source_count BIGINT, grouped_count BIGINT, status STRING"
        ),
        "expected_rows": 48,
        "target_scope": "snapshot_id IN ('selection-2021-2023-20260929', 'development-2024-20260929')",
    },
    "series_manifest": {
        "fields": (
            "experiment_id",
            "series_id",
            "selection_rank",
            "inclusion_status",
            "reason",
            "positive_days",
            "median_daily_count",
            "active_span_days",
            "selection_data_hash",
            "mapping_hash",
        ),
        "keys": ("experiment_id", "series_id"),
        "schema": (
            "experiment_id STRING, series_id STRING, selection_rank INT, "
            "inclusion_status STRING, reason STRING, positive_days INT, "
            "median_daily_count DOUBLE, active_span_days INT, "
            "selection_data_hash STRING, mapping_hash STRING"
        ),
        "expected_rows": 1245,
        "target_scope": "experiment_id = 'nyc311-benchmark-v1'",
    },
}


def source_sql(path: str, table: str) -> str:
    spec = TABLES[table]
    fields = [
        "CAST(extracted_at AS TIMESTAMP) AS extracted_at" if name == "extracted_at" else name
        for name in spec["fields"]
    ]
    return (
        f"SELECT {', '.join(fields)} FROM read_files('{path}', format => 'json', "
        f"schema => '{spec['schema']}')"
    )


def load_table(api, warehouse_id: str, target: str, path: str, table: str) -> dict:
    spec = TABLES[table]
    source = source_sql(path, table)
    fields = spec["fields"]
    keys = spec["keys"]
    query_ids = {}
    query_ids["count"], rows = run_query(
        api, warehouse_id, f"WITH source AS ({source}) SELECT COUNT(*) FROM source"
    )
    if int(rows[0][0]) != spec["expected_rows"]:
        raise ValueError(f"Unexpected staged {table} row count")
    query_ids["duplicates"], rows = run_query(
        api,
        warehouse_id,
        f"WITH source AS ({source}) SELECT COUNT(*) FROM ("
        f"SELECT {', '.join(keys)} FROM source GROUP BY {', '.join(keys)} "
        "HAVING COUNT(*) > 1)",
    )
    if int(rows[0][0]) != 0:
        raise ValueError(f"Duplicate staged {table} keys")
    conditions = " AND ".join(f"target.{key} = source.{key}" for key in keys)
    query_ids["merge"], _ = run_query(
        api,
        warehouse_id,
        f"MERGE INTO {target} AS target USING ({source}) AS source ON {conditions} "
        f"WHEN NOT MATCHED THEN INSERT ({', '.join(fields)}) VALUES "
        f"({', '.join('source.' + field for field in fields)})",
        timeout_seconds=600,
    )
    columns = ", ".join(fields)
    query_ids["compare"], rows = run_query(
        api,
        warehouse_id,
        f"WITH source AS ({source}), target AS (SELECT {columns} FROM {target} "
        f"WHERE {spec['target_scope']}) "
        "SELECT (SELECT COUNT(*) FROM target), "
        "(SELECT COUNT(*) FROM (SELECT * FROM source EXCEPT ALL SELECT * FROM target)), "
        "(SELECT COUNT(*) FROM (SELECT * FROM target EXCEPT ALL SELECT * FROM source))",
        timeout_seconds=300,
    )
    persisted, missing, extra = map(int, rows[0])
    if (persisted, missing, extra) != (spec["expected_rows"], 0, 0):
        raise ValueError(
            f"Persisted {table} differs from staged source; query {query_ids['compare']}"
        )
    return {
        "table": target,
        "rows": persisted,
        "missing_rows": missing,
        "extra_rows": extra,
        "query_ids": query_ids,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
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
    manifest = json.loads((STAGE / "manifest.json").read_text(encoding="utf-8"))
    for table in TABLES:
        path = STAGE / f"{table}.jsonl"
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest[f"{table}_sha256"]:
            raise ValueError(f"Local {table} stage payload hash mismatch")
    client = WorkspaceClient(profile=config.workspace_profile)
    if client.config.host.rstrip("/") != config.workspace_host.rstrip("/"):
        raise ValueError("Authenticated workspace host differs from config")
    results = []
    for table in TABLES:
        file_path = f"/Volumes/{config.catalog}/{config.schema}/artifacts/{manifest['stage_id']}/{table}.jsonl"
        results.append(
            load_table(
                client.statement_execution,
                config.warehouse_id,
                f"{config.catalog}.{config.schema}.{table}",
                file_path,
                table,
            )
        )
    evidence = {
        "status": "verified",
        "stage_id": manifest["stage_id"],
        "source_partitions_sha256": manifest["source_partitions_sha256"],
        "series_manifest_sha256": manifest["series_manifest_sha256"],
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
