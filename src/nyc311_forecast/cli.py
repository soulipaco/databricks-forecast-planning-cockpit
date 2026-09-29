"""Small local command surface; cloud commands are added only when executable."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from nyc311_forecast.config import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nyc311")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="Validate local configuration and report workspace inputs")
    doctor.add_argument("--config", type=Path, required=True)
    ingest = sub.add_parser("ingest", help="Extract reconciled monthly NYC aggregates")
    ingest.add_argument("--start", type=date.fromisoformat, required=True)
    ingest.add_argument("--end", type=date.fromisoformat, required=True)
    ingest.add_argument("--snapshot-id", required=True)
    ingest.add_argument("--output-dir", type=Path, default=Path("data/snapshots"))
    ingest.add_argument("--version", choices=("soda2", "soda3"), default="soda2")
    ingest.add_argument("--page-size", type=int, default=1000)
    select = sub.add_parser("select-series", help="Freeze series from a complete 2021–2023 snapshot")
    select.add_argument("--config", type=Path, required=True)
    select.add_argument("--snapshot-dir", type=Path, required=True)
    select.add_argument("--output", type=Path, required=True)
    smoke = sub.add_parser("smoke", help="Run the pinned v2 SQL capability check")
    smoke.add_argument("--config", type=Path, required=True)
    materialize = sub.add_parser("materialize-development", help="Build verified 2021–2024 daily Silver rows")
    materialize.add_argument("--selection-snapshot", type=Path, required=True)
    materialize.add_argument("--development-snapshot", type=Path, required=True)
    materialize.add_argument("--series-manifest", type=Path, required=True)
    materialize.add_argument("--snapshot-id", required=True)
    materialize.add_argument("--output-dir", type=Path, default=Path("data/silver"))
    args = parser.parse_args(argv)
    if args.command == "doctor":
        try:
            config = load_config(args.config)
        except (OSError, ValueError, TypeError) as exc:
            print(f"Configuration invalid: {exc}", file=sys.stderr)
            return 2
        print(json.dumps({
            "config_valid": True,
            "experiment_id": config.experiment_id,
            "snapshot_id": config.snapshot_id,
            "workspace_configured": bool(config.workspace_host and config.warehouse_id and config.catalog and config.schema),
            "workspace_verified": False,
        }, indent=2))
        return 0
    if args.command == "ingest":
        from nyc311_forecast.ingest.client import SourceError
        from nyc311_forecast.ingest.snapshot import extract_snapshot

        try:
            path = extract_snapshot(args.start, args.end, args.output_dir, args.snapshot_id, version=args.version, page_size=args.page_size)
        except (OSError, ValueError, SourceError) as exc:
            print(f"Ingest failed: {exc}", file=sys.stderr)
            return 2
        print(path)
        return 0
    if args.command == "select-series":
        from nyc311_forecast.data.selection import select_from_snapshot

        try:
            config = load_config(args.config)
            path = select_from_snapshot(
                args.snapshot_dir, config.experiment_id, args.output,
                expected_snapshot_id=config.snapshot_id,
            )
        except (OSError, ValueError, TypeError, KeyError) as exc:
            print(f"Selection failed: {exc}", file=sys.stderr)
            return 2
        print(path)
        return 0
    if args.command == "materialize-development":
        from nyc311_forecast.data.materialize import materialize_development

        try:
            path = materialize_development(
                args.selection_snapshot, args.development_snapshot,
                args.series_manifest, args.output_dir, snapshot_id=args.snapshot_id,
            )
        except (OSError, ValueError, TypeError, KeyError) as exc:
            print(f"Materialization failed: {exc}", file=sys.stderr)
            return 2
        print(path)
        return 0
    if args.command == "smoke":
        try:
            from databricks.sdk import WorkspaceClient
            from databricks.sdk.errors import DatabricksError

            from nyc311_forecast.platform.smoke import run_v2_smoke
        except ImportError as exc:
            print(f"Smoke requires the platform extra: {exc}", file=sys.stderr)
            return 2
        try:
            config = load_config(args.config)
            if not config.workspace_host or not config.warehouse_id:
                raise ValueError("workspace_host and warehouse_id are required")
            client = WorkspaceClient(profile=config.workspace_profile) if config.workspace_profile else WorkspaceClient()
            if client.config.host.rstrip("/") != config.workspace_host.rstrip("/"):
                raise ValueError("Authenticated workspace host differs from config")
            result = run_v2_smoke(client.statement_execution, config.warehouse_id)
        except (OSError, ValueError, TypeError, RuntimeError, TimeoutError, DatabricksError) as exc:
            print(f"Smoke failed: {exc}", file=sys.stderr)
            return 2
        print(json.dumps({"status": "workspace_verified", "model_id": result.model_id, "query_id": result.lineage["query_id"], "forecast_rows": len(result.predictions), "wall_seconds": result.wall_seconds}, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
