"""Create and verify an unpublished development-data dashboard draft."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.dashboards import Dashboard
from verify_workspace_silver import ROOT, run_query

from nyc311_forecast.config import load_config

DASHBOARD = ROOT / "dashboards/development_readiness.lvdash.json"
EXPORTED = ROOT / "evidence/development_readiness_export_20260929.lvdash.json"
DISPLAY_NAME = "NYC 311 Forecast Planning — Development Readiness"


def validate_definition(definition: dict) -> str:
    datasets = definition["datasets"]
    pages = definition["pages"]
    if len(datasets) != 1 or datasets[0]["name"] != "development_series":
        raise ValueError("Expected exactly one development series dataset")
    if len(pages) != 1 or pages[0]["name"] != "readiness":
        raise ValueError("Expected exactly one readiness page")
    query = "".join(datasets[0]["queryLines"])
    if "FROM daily_requests " not in query or "ai_forecast(" in query.lower():
        raise ValueError("Dashboard dataset must read materialized development Silver only")
    if "development-silver-20260929" not in query:
        raise ValueError("Dashboard dataset must pin the verified snapshot")
    widgets = [item["widget"] for item in pages[0]["layout"]]
    if not any(
        "no three-model benchmark"
        in "".join(widget.get("multilineTextboxSpec", {}).get("lines", []))
        for widget in widgets
    ):
        raise ValueError("Dashboard must clearly label unavailable benchmark results")
    return query


def canonical_definition(definition: dict) -> dict:
    """Ignore dataset defaults and line joining added by the Lakeview API."""
    result = copy.deepcopy(definition)
    for dataset in result["datasets"]:
        dataset.pop("catalog", None)
        dataset.pop("schema", None)
        dataset["queryLines"] = ["".join(dataset["queryLines"])]
    for page in result["pages"]:
        for item in page.get("layout", []):
            text = item["widget"].get("multilineTextboxSpec")
            if text:
                text["lines"] = ["".join(text["lines"])]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prior = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else None
    if prior and prior["definition_sha256"] != hashlib.sha256(DASHBOARD.read_bytes()).hexdigest():
        raise ValueError("Existing draft evidence refers to a different definition")
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
    content = DASHBOARD.read_text(encoding="utf-8")
    definition = json.loads(content)
    query = validate_definition(definition)
    client = WorkspaceClient(profile=config.workspace_profile)
    if client.config.host.rstrip("/") != config.workspace_host.rstrip("/"):
        raise ValueError("Authenticated workspace host differs from config")
    preflight_sql = query.replace(
        "FROM daily_requests ", f"FROM {config.catalog}.{config.schema}.daily_requests ", 1
    )
    query_id, rows = run_query(client.statement_execution, config.warehouse_id, preflight_sql)
    if not rows or (
        len(rows),
        sum(int(row[3]) for row in rows),
        sum(int(row[4]) for row in rows),
    ) != (21, 5_088_270, 40):
        raise ValueError("Dashboard dataset query did not match the verified Silver snapshot")
    dashboard = (
        client.lakeview.get(prior["dashboard_id"])
        if prior
        else client.lakeview.create(
            Dashboard(
                display_name=DISPLAY_NAME,
                warehouse_id=config.warehouse_id,
                serialized_dashboard=content,
            ),
            dataset_catalog=config.catalog,
            dataset_schema=config.schema,
        )
    )
    if not dashboard.dashboard_id:
        raise RuntimeError("Dashboard creation returned no ID")
    evidence = {
        "status": "draft_created_pending_verification",
        "dashboard_id": dashboard.dashboard_id,
        "warehouse_id": config.warehouse_id,
        "catalog": config.catalog,
        "schema": config.schema,
        "definition_sha256": hashlib.sha256(DASHBOARD.read_bytes()).hexdigest(),
        "dataset_preflight_query_id": query_id,
        "dataset_rows": len(rows),
        "dataset_requests": sum(int(row[3]) for row in rows),
        "dataset_zero_filled_days": sum(int(row[4]) for row in rows),
        "published": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    retrieved = client.lakeview.get(dashboard.dashboard_id)
    if canonical_definition(
        json.loads(retrieved.serialized_dashboard or "null")
    ) != canonical_definition(definition):
        raise ValueError(f"Stored dashboard definition differs; ID {dashboard.dashboard_id}")
    if retrieved.warehouse_id != config.warehouse_id:
        raise ValueError(f"Stored dashboard warehouse differs; ID {dashboard.dashboard_id}")
    if not retrieved.path:
        raise ValueError(f"Stored dashboard has no workspace path; ID {dashboard.dashboard_id}")
    with client.workspace.download(retrieved.path) as stream:
        exported_bytes = stream.read()
    exported = json.loads(exported_bytes.decode("utf-8"))
    if canonical_definition(exported) != canonical_definition(definition):
        raise ValueError(f"Exported dashboard differs; ID {dashboard.dashboard_id}")
    EXPORTED.parent.mkdir(parents=True, exist_ok=True)
    EXPORTED.write_bytes(exported_bytes)
    evidence["status"] = "draft_verified"
    evidence["export_sha256"] = hashlib.sha256(exported_bytes).hexdigest()
    evidence["export_artifact"] = str(EXPORTED.relative_to(ROOT)).replace("\\", "/")
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
