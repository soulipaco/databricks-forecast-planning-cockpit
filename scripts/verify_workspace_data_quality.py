"""Reconcile the serving data-quality view with source and Silver manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from databricks.sdk import WorkspaceClient
from verify_workspace_silver import run_query

from nyc311_forecast.config import load_config

EXPECTED = {
    ("selection-2021-2023-20260929", "source_partitions"): (36, 36, 36, 9_615_565, None, None),
    ("development-2024-20260929", "source_partitions"): (12, 12, 12, 3_456_769, None, None),
    ("development-silver-20260929", "selected_series_silver"): (
        None,
        None,
        None,
        5_088_270,
        30_681,
        40,
    ),
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
    client = WorkspaceClient(profile=config.workspace_profile)
    if client.config.host.rstrip("/") != config.workspace_host.rstrip("/"):
        raise ValueError("Authenticated workspace host differs from config")
    query_id, data = run_query(
        client.statement_execution,
        config.warehouse_id,
        "SELECT snapshot_id, data_kind, expected_partitions, observed_partitions, "
        "reconciled_partitions, request_count, series_days, zero_filled_days "
        f"FROM {config.catalog}.{config.schema}.v_data_quality ORDER BY snapshot_id",
    )
    observed = {
        (row[0], row[1]): tuple(None if value is None else int(value) for value in row[2:])
        for row in data
    }
    if observed != EXPECTED:
        raise ValueError(f"Data-quality view differs from source manifests; query ID {query_id}")
    evidence = {
        "status": "verified",
        "query_id": query_id,
        "rows": [
            {
                "snapshot_id": key[0],
                "data_kind": key[1],
                "expected_partitions": values[0],
                "observed_partitions": values[1],
                "reconciled_partitions": values[2],
                "request_count": values[3],
                "series_days": values[4],
                "zero_filled_days": values[5],
            }
            for key, values in sorted(observed.items())
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
