"""Stage and idempotently persist the labeled local development smoke slice."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from databricks.sdk import WorkspaceClient
from verify_workspace_silver import ROOT, run_query

from nyc311_forecast.config import load_config
from nyc311_forecast.platform.persist_smoke import FIELDS, KEYS, SCHEMAS, STATUS, stage

SOURCE = ROOT / "evidence/development_slice_20260929.json"
STAGE = ROOT / "data/workspace_stage/development-smoke-20260929"
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
RUN_ID = re.compile(r"development-slice-[a-f0-9]{12}\Z")


def source_sql(path: str, table: str) -> str:
    casts = {"origin": "DATE", "ds": "DATE", "started_at": "TIMESTAMP", "ended_at": "TIMESTAMP"}
    columns = [f"CAST({name} AS {casts[name]}) AS {name}" if name in casts else name
               for name in FIELDS[table]]
    return (f"SELECT {', '.join(columns)} FROM read_files('{path}', format => 'json', "
            f"schema => '{SCHEMAS[table]}')")


def persist_table(api, warehouse_id: str, target: str, path: str, table: str,
                  run_id: str, expected_rows: int) -> dict:
    if table not in FIELDS or not RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid table/run scope")
    source = source_sql(path, table)
    fields = FIELDS[table]
    keys = KEYS[table]
    q = {}
    q["preflight"], rows = run_query(
        api, warehouse_id,
        f"WITH source AS ({source}) SELECT COUNT(*), "
        f"SUM(CASE WHEN run_id = '{run_id}' THEN 0 ELSE 1 END) FROM source")
    if tuple(map(int, rows[0])) != (expected_rows, 0):
        raise ValueError(f"Staged {table} row count/scope differs; query {q['preflight']}")
    q["duplicates"], rows = run_query(
        api, warehouse_id,
        f"WITH source AS ({source}) SELECT COUNT(*) FROM "
        f"(SELECT {', '.join(keys)} FROM source GROUP BY {', '.join(keys)} HAVING COUNT(*) > 1)")
    if int(rows[0][0]):
        raise ValueError(f"Duplicate staged {table} keys; query {q['duplicates']}")
    conditions = " AND ".join(f"target.{key} = source.{key}" for key in keys)
    q["merge"], _ = run_query(
        api, warehouse_id,
        f"MERGE INTO {target} AS target USING ({source}) AS source ON {conditions} "
        f"WHEN NOT MATCHED THEN INSERT ({', '.join(fields)}) "
        f"VALUES ({', '.join('source.' + field for field in fields)})",
        timeout_seconds=600)
    columns = ", ".join(fields)
    q["readback"], rows = run_query(
        api, warehouse_id,
        f"WITH source AS ({source}), target AS "
        f"(SELECT {columns} FROM {target} WHERE run_id = '{run_id}') "
        "SELECT (SELECT COUNT(*) FROM target), "
        "(SELECT COUNT(*) FROM (SELECT * FROM source EXCEPT ALL SELECT * FROM target)), "
        "(SELECT COUNT(*) FROM (SELECT * FROM target EXCEPT ALL SELECT * FROM source))",
        timeout_seconds=300)
    persisted, missing, extra = map(int, rows[0])
    result = {"table": target, "expected_rows": expected_rows, "persisted_rows": persisted,
              "missing_rows": missing, "extra_rows": extra, "query_ids": q}
    if (persisted, missing, extra) != (expected_rows, 0, 0):
        raise ValueError(f"Persisted {table} differs from source; query {q['readback']}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output evidence exists; choose a new path")
    config = load_config(args.config)
    if not all((config.workspace_host, config.workspace_profile, config.warehouse_id,
                config.catalog, config.schema)):
        raise ValueError("Workspace host, profile, warehouse, catalog and schema required")
    if any(not IDENTIFIER.fullmatch(value) for value in (config.catalog, config.schema)):
        raise ValueError("Invalid target identifier")
    manifest = stage(SOURCE, STAGE)
    if manifest["status"] != STATUS or not RUN_ID.fullmatch(manifest["run_id"]):
        raise ValueError("Only the labeled smoke slice is allowed")
    client = WorkspaceClient(profile=config.workspace_profile)
    if client.config.host.rstrip("/") != config.workspace_host.rstrip("/"):
        raise ValueError("Authenticated workspace host differs from config")
    volume_dir = f"/Volumes/{config.catalog}/{config.schema}/artifacts/{manifest['stage_id']}"
    client.files.create_directory(volume_dir)
    results = []
    for table, info in manifest["tables"].items():
        local = STAGE / f"{table}.jsonl"
        if hashlib.sha256(local.read_bytes()).hexdigest() != info["sha256"]:
            raise ValueError(f"Local {table} stage hash differs from manifest")
        remote = f"{volume_dir}/{table}.jsonl"
        with local.open("rb") as stream:
            client.files.upload(remote, stream, overwrite=True)
        results.append(persist_table(
            client.statement_execution, config.warehouse_id,
            f"{config.catalog}.{config.schema}.{table}", remote, table,
            manifest["run_id"], info["rows"]))
    evidence = {"status": "verified_smoke_only_not_benchmark", "run_id": manifest["run_id"],
                "stage_id": manifest["stage_id"], "source_sha256": manifest["source_sha256"],
                "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
