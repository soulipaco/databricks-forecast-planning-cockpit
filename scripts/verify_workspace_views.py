"""Query each deployed serving view and store the workspace query IDs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from databricks.sdk import WorkspaceClient
from verify_workspace_silver import run_query

from nyc311_forecast.config import load_config

VIEWS = (
    "v_forecast_detail",
    "v_planning_gap",
    "v_model_leaderboard_cells",
    "v_run_health",
    "v_data_quality",
)


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
    result = []
    for name in VIEWS:
        query_id, data = run_query(
            client.statement_execution,
            config.warehouse_id,
            f"SELECT COUNT(*) FROM {config.catalog}.{config.schema}.{name}",
        )
        result.append({"view": name, "query_id": query_id, "rows": int(data[0][0])})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
