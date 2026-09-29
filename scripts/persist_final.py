"""Persist the frozen final three-model benchmark to Delta and verify exact readback."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from databricks.sdk import WorkspaceClient
from persist_development_compare import persist_table
from verify_workspace_silver import ROOT

from nyc311_forecast.config import load_config
from nyc311_forecast.platform.persist_final import RUN_ID, stage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output evidence exists; choose a new path")
    config = load_config(args.config)
    freeze = json.loads((ROOT / "evidence/freeze_manifest.json").read_text(encoding="utf-8"))
    source = json.loads(args.input.read_text(encoding="utf-8"))
    silver = ROOT / "data/silver" / source["silver_snapshot_id"] / "daily_requests.jsonl"
    if hashlib.sha256(silver.read_bytes()).hexdigest() != source["silver_sha256"]:
        raise ValueError("Local Silver differs from the benchmark input")
    stage_dir = ROOT / "data/workspace_stage" / source["run_id"]
    manifest = stage(args.input, stage_dir, protocol_hash=freeze["hashes"]["protocol"],
                     config_hash=freeze["hashes"]["config"])
    client = WorkspaceClient(profile=config.workspace_profile)
    if client.config.host.rstrip("/") != config.workspace_host.rstrip("/"):
        raise ValueError("Authenticated workspace host differs from config")
    remote_dir = f"/Volumes/{config.catalog}/{config.schema}/artifacts/{manifest['stage_id']}"
    client.files.create_directory(remote_dir)
    results = []
    for table, info in manifest["tables"].items():
        remote = f"{remote_dir}/{table}.jsonl"
        with (stage_dir / f"{table}.jsonl").open("rb") as stream:
            client.files.upload(remote, stream, overwrite=True)
        results.append(persist_table(
            client.statement_execution, config.warehouse_id,
            f"{config.catalog}.{config.schema}.{table}", remote, table,
            manifest["run_id"], info["rows"], run_pattern=RUN_ID))
    evidence = {"status": "verified_final_three_model_persisted", **{
        k: manifest[k] for k in ("run_id", "stage_id", "source_sha256", "expected_cells",
                                 "complete_cells", "failed_cells")},
        "silver_snapshot_id": source["silver_snapshot_id"], "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in evidence.items() if k != "results"} | {
        "tables": {r["table"].split(".")[-1]: (r["persisted_rows"], r["missing_rows"],
                                               r["extra_rows"]) for r in results}}, indent=2))


if __name__ == "__main__":
    main()
