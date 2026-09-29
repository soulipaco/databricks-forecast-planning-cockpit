"""Reconcile serving-view 2024 two-model paired sums with local evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from databricks.sdk import WorkspaceClient
from verify_workspace_silver import run_query

from nyc311_forecast.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--diagnostic", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Evidence output already exists")
    config = load_config(args.config)
    if not all(
        (
            config.workspace_profile,
            config.workspace_host,
            config.warehouse_id,
            config.catalog,
            config.schema,
        )
    ):
        raise ValueError("Workspace configuration incomplete")
    expected = json.loads(args.diagnostic.read_text(encoding="utf-8"))
    if (
        expected["status"] != "two_model_2024_development_diagnostic_only"
        or expected["paired_series_origin_pairs"] != 42
    ):
        raise ValueError("Expected a complete, paired 2024 development diagnostic")
    run_id = expected["run_id"]
    if not run_id.startswith("development-two-model-") or len(run_id) != 34:
        raise ValueError("Unexpected development run ID")
    client = WorkspaceClient(profile=config.workspace_profile)
    if client.config.host.rstrip("/") != config.workspace_host.rstrip("/"):
        raise ValueError("Authenticated workspace differs from config")
    sql = (
        "SELECT model_id, COUNT(*) AS cells, SUM(abs_error_sum) AS abs_error_sum, "
        "SUM(actual_sum) AS actual_sum FROM "
        f"{config.catalog}.{config.schema}.v_model_leaderboard_cells "
        f"WHERE run_id = '{run_id}' AND horizon_days = 28 "
        "AND n_expected = 28 AND n_actual = 28 AND n_predictions = 28 "
        "GROUP BY model_id ORDER BY model_id"
    )
    query_id, rows = run_query(client.statement_execution, config.warehouse_id, sql)
    observed = {}
    for model_id, count, abs_sum, actual_sum in rows or []:
        if model_id not in expected["models"] or model_id in observed:
            raise ValueError("Unexpected model in serving view")
        reference = expected["models"][model_id]
        if (
            int(count) != 42
            or abs(float(abs_sum) - reference["paired_abs_error_sum"]) > 1e-6
            or abs(float(actual_sum) - reference["paired_actual_sum"]) > 1e-6
        ):
            raise ValueError(f"Serving view does not reconcile for {model_id}; query {query_id}")
        observed[model_id] = {
            "cells": int(count),
            "abs_error_sum": float(abs_sum),
            "actual_sum": float(actual_sum),
        }
    if set(observed) != {"snaive7", "prophet_tuned"}:
        raise ValueError("Serving view lacks a development model")
    result = {
        "status": "verified_two_model_development_scores_only",
        "run_id": run_id,
        "query_id": query_id,
        "models": observed,
        "limitation": "No native v2 or 2025 final evaluation",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
