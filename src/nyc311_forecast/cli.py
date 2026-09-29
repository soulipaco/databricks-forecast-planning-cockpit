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
            path = extract_snapshot(args.start, args.end, args.output_dir, args.snapshot_id, version=args.version)
        except (OSError, ValueError, SourceError) as exc:
            print(f"Ingest failed: {exc}", file=sys.stderr)
            return 2
        print(path)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
