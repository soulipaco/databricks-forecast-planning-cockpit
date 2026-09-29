"""Persist a completed 21-series, two-model development run; never a benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from databricks.sdk import WorkspaceClient
from verify_workspace_silver import ROOT, run_query

from nyc311_forecast.config import load_config
from nyc311_forecast.platform.persist_development import RUN_ID, STATUS, stage
from nyc311_forecast.platform.persist_smoke import FIELDS, KEYS, SCHEMAS


def source_sql(path: str, table: str) -> str:
    casts = {"origin": "DATE", "ds": "DATE", "started_at": "TIMESTAMP", "ended_at": "TIMESTAMP"}
    columns = [f"CAST({name} AS {casts[name]}) AS {name}" if name in casts else name
               for name in FIELDS[table]]
    return (f"SELECT {', '.join(columns)} FROM read_files('{path}', format => 'json', "
            f"schema => '{SCHEMAS[table]}')")


def persist_table(api, warehouse_id: str, target: str, path: str, table: str,
                  run_id: str, expected_rows: int, run_pattern=RUN_ID) -> dict:
    if table not in FIELDS or not run_pattern.fullmatch(run_id):
        raise ValueError("Invalid table/run scope")
    source = source_sql(path, table)
    fields, keys = FIELDS[table], KEYS[table]
    q = {}
    q["preflight"], rows = run_query(
        api, warehouse_id, f"WITH source AS ({source}) SELECT COUNT(*), "
        f"COALESCE(SUM(CASE WHEN run_id = '{run_id}' THEN 0 ELSE 1 END), 0) FROM source")
    if tuple(map(int, rows[0])) != (expected_rows, 0):
        raise ValueError(f"Staged {table} count/scope mismatch; query {q['preflight']}")
    q["duplicates"], rows = run_query(
        api, warehouse_id, f"WITH source AS ({source}) SELECT COUNT(*) FROM "
        f"(SELECT {', '.join(keys)} FROM source GROUP BY {', '.join(keys)} HAVING COUNT(*) > 1)")
    if int(rows[0][0]):
        raise ValueError(f"Duplicate staged {table} keys; query {q['duplicates']}")
    conditions = " AND ".join(f"target.{key} = source.{key}" for key in keys)
    q["merge"], _ = run_query(
        api, warehouse_id, f"MERGE INTO {target} AS target USING ({source}) AS source "
        f"ON {conditions} WHEN NOT MATCHED THEN INSERT ({', '.join(fields)}) "
        f"VALUES ({', '.join('source.' + field for field in fields)})", timeout_seconds=600)
    columns = ", ".join(fields)
    q["readback"], rows = run_query(
        api, warehouse_id, f"WITH source AS ({source}), target AS "
        f"(SELECT {columns} FROM {target} WHERE run_id = '{run_id}') "
        "SELECT (SELECT COUNT(*) FROM target), "
        "(SELECT COUNT(*) FROM (SELECT * FROM source EXCEPT ALL SELECT * FROM target)), "
        "(SELECT COUNT(*) FROM (SELECT * FROM target EXCEPT ALL SELECT * FROM source))",
        timeout_seconds=300)
    persisted, missing, extra = map(int, rows[0])
    result = {"table": target, "expected_rows": expected_rows, "persisted_rows": persisted,
              "missing_rows": missing, "extra_rows": extra, "query_ids": q}
    if (persisted, missing, extra) != (expected_rows, 0, 0):
        raise ValueError(f"Persisted {table} differs from staged source; query {q['readback']}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output evidence file exists; choose a new path")
    if not args.input.exists():
        raise FileNotFoundError("Development model output is required before persistence")
    config = load_config(args.config)
    if not all((config.workspace_host, config.workspace_profile, config.warehouse_id,
                config.catalog, config.schema)):
        raise ValueError("Workspace host, profile, warehouse, catalog and schema required")
    source = json.loads(args.input.read_text(encoding="utf-8"))
    if not RUN_ID.fullmatch(source.get("run_id", "")):
        raise ValueError("Input is not a full two-model development run")
    lineage_files = {
        "selection_sha256": ROOT / "data/series_manifest/selection-v1.json",
        "silver_sha256": ROOT / "data/silver/development-silver-20260929/daily_requests.jsonl",
        "tuning_manifest_sha256": ROOT / "evidence/development_tuning_full_20260929/manifest.json",
    }
    for name, path in lineage_files.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != source.get(name):
            raise ValueError(f"Local {name} differs from model output")
    for index, series_id in enumerate(source["series_ids"]):
        path = ROOT / "evidence/development_tuning_full_20260929" / f"series-{index:02d}.json"
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["tuning_checkpoint_sha256_by_series"].get(series_id):
            raise ValueError(f"Tuning checkpoint differs for {series_id}")
    stage_dir = ROOT / "data/workspace_stage" / source["run_id"]
    manifest = stage(args.input, stage_dir)
    if manifest["status"] != STATUS:
        raise ValueError("Expected partial two-model development status")
    client = WorkspaceClient(profile=config.workspace_profile)
    if client.config.host.rstrip("/") != config.workspace_host.rstrip("/"):
        raise ValueError("Authenticated workspace host differs from config")
    remote_dir = f"/Volumes/{config.catalog}/{config.schema}/artifacts/{manifest['stage_id']}"
    client.files.create_directory(remote_dir)
    results = []
    for table, info in manifest["tables"].items():
        local = stage_dir / f"{table}.jsonl"
        if hashlib.sha256(local.read_bytes()).hexdigest() != info["sha256"]:
            raise ValueError(f"Local {table} stage hash mismatch")
        remote = f"{remote_dir}/{table}.jsonl"
        with local.open("rb") as stream:
            client.files.upload(remote, stream, overwrite=True)
        results.append(persist_table(
            client.statement_execution, config.warehouse_id,
            f"{config.catalog}.{config.schema}.{table}", remote, table,
            manifest["run_id"], info["rows"]))
    evidence = {"status": "verified_partial_two_model_development_not_benchmark",
                "run_id": manifest["run_id"], "stage_id": manifest["stage_id"],
                "source_sha256": manifest["source_sha256"],
                "silver_snapshot_id": source["silver_snapshot_id"],
                "silver_sha256": source["silver_sha256"],
                "selection_sha256": source["selection_sha256"],
                "tuning_manifest_sha256": source["tuning_manifest_sha256"],
                "model_ids": source["model_ids"], "origins": source["origins"],
                "expected_cells": manifest["expected_cells"], "complete_cells": manifest["complete_cells"],
                "failed_cells": manifest["failed_cells"],
                "paired_two_model_cells": manifest["paired_two_model_cells"],
                "evaluation_cells_include_failures": True, "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
