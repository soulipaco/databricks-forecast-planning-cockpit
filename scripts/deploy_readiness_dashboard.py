"""Create and verify an unpublished development-data dashboard draft."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound
from databricks.sdk.service.dashboards import Dashboard
from verify_workspace_data_quality import EXPECTED as EXPECTED_QUALITY
from verify_workspace_silver import ROOT, run_query

from nyc311_forecast.config import load_config

DASHBOARD = ROOT / "dashboards/development_readiness.lvdash.json"
EXPORTED = ROOT / "evidence/development_readiness_quality_export_20260929.lvdash.json"
DISPLAY_NAME = "NYC 311 Forecast Planning — Development Readiness"


def validate_definition(definition: dict) -> dict[str, str]:
    datasets = definition["datasets"]
    pages = definition["pages"]
    if [dataset["name"] for dataset in datasets] != ["development_series", "data_quality"]:
        raise ValueError("Expected development series and data quality datasets")
    if len(pages) != 1 or pages[0]["name"] != "readiness":
        raise ValueError("Expected exactly one readiness page")
    queries = {dataset["name"]: "".join(dataset["queryLines"]) for dataset in datasets}
    if "FROM daily_requests " not in queries["development_series"]:
        raise ValueError("Dashboard dataset must read materialized development Silver only")
    if "development-silver-20260929" not in queries["development_series"]:
        raise ValueError("Dashboard dataset must pin the verified snapshot")
    if "FROM v_data_quality " not in queries["data_quality"] or not all(
        snapshot in queries["data_quality"] for snapshot, _ in EXPECTED_QUALITY
    ):
        raise ValueError("Data quality dataset must pin the three verified populations")
    if any("ai_forecast(" in query.lower() for query in queries.values()):
        raise ValueError("Dashboard datasets must not invoke forecasting")
    widgets = [item["widget"] for item in pages[0]["layout"]]
    if not any(
        "no three-model benchmark"
        in "".join(widget.get("multilineTextboxSpec", {}).get("lines", []))
        for widget in widgets
    ):
        raise ValueError("Dashboard must clearly label unavailable benchmark results")
    tables = {widget["name"]: widget for widget in widgets if widget.get("spec", {}).get("widgetType") == "table"}
    if set(tables) != {"development_series_table", "data_quality_table"}:
        raise ValueError("Expected both readiness tables")
    for name, dataset in (("development_series_table", "development_series"), ("data_quality_table", "data_quality")):
        widget = tables[name]
        binding = widget["queries"][0]["query"]
        fields = {field["name"] for field in binding["fields"]}
        columns = {column["fieldName"] for column in widget["spec"]["encodings"]["columns"]}
        if binding["datasetName"] != dataset or fields != columns:
            raise ValueError(f"Incorrect table binding: {name}")
    return queries


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
    parser.add_argument("--prior-evidence", type=Path, help="Verified draft evidence to update in place")
    args = parser.parse_args()
    current = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else None
    prior = current or (json.loads(args.prior_evidence.read_text(encoding="utf-8")) if args.prior_evidence else None)
    definition_sha = hashlib.sha256(DASHBOARD.read_bytes()).hexdigest()
    if current and current["definition_sha256"] != definition_sha:
        raise ValueError("Existing draft evidence refers to a different definition")
    if prior and (prior.get("published") is not False or not prior.get("dashboard_id")):
        raise ValueError("Only a recorded unpublished dashboard draft may be updated")
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
    queries = validate_definition(definition)
    client = WorkspaceClient(profile=config.workspace_profile)
    if client.config.host.rstrip("/") != config.workspace_host.rstrip("/"):
        raise ValueError("Authenticated workspace host differs from config")
    preflight_sql = queries["development_series"].replace(
        "FROM daily_requests ", f"FROM {config.catalog}.{config.schema}.daily_requests ", 1
    )
    query_id, rows = run_query(client.statement_execution, config.warehouse_id, preflight_sql)
    if not rows or (
        len(rows),
        sum(int(row[3]) for row in rows),
        sum(int(row[4]) for row in rows),
    ) != (21, 5_088_270, 40):
        raise ValueError("Dashboard dataset query did not match the verified Silver snapshot")
    quality_sql = queries["data_quality"].replace(
        "FROM v_data_quality ", f"FROM {config.catalog}.{config.schema}.v_data_quality ", 1
    )
    quality_query_id, quality_rows = run_query(
        client.statement_execution, config.warehouse_id, quality_sql
    )
    quality_observed = {
        (row[0], row[1]): tuple(None if value is None else int(value) for value in row[2:])
        for row in quality_rows or []
    }
    if quality_observed != EXPECTED_QUALITY:
        raise ValueError(f"Dashboard data-quality query differs from verified populations; query ID {quality_query_id}")
    if prior:
        existing = client.lakeview.get(prior["dashboard_id"])
        if existing.warehouse_id != config.warehouse_id:
            raise ValueError("Existing dashboard warehouse differs from config")
        if args.prior_evidence and not current:
            old_export = ROOT / prior["export_artifact"]
            if hashlib.sha256(old_export.read_bytes()).hexdigest() != prior["export_sha256"]:
                raise ValueError("Prior export hash differs from evidence")
            if canonical_definition(json.loads(existing.serialized_dashboard or "null")) != canonical_definition(json.loads(old_export.read_text(encoding="utf-8"))):
                raise ValueError("Workspace draft differs from the prior verified export")
            dashboard = client.lakeview.update(
                prior["dashboard_id"],
                Dashboard(display_name=DISPLAY_NAME, warehouse_id=config.warehouse_id, serialized_dashboard=content),
                dataset_catalog=config.catalog,
                dataset_schema=config.schema,
            )
        else:
            dashboard = existing
    else:
        dashboard = client.lakeview.create(
            Dashboard(
                display_name=DISPLAY_NAME,
                warehouse_id=config.warehouse_id,
                serialized_dashboard=content,
            ),
            dataset_catalog=config.catalog,
            dataset_schema=config.schema,
        )
    if not dashboard.dashboard_id:
        raise RuntimeError("Dashboard creation returned no ID")
    evidence = {
        "status": "draft_created_pending_verification",
        "dashboard_id": dashboard.dashboard_id,
        "warehouse_id": config.warehouse_id,
        "catalog": config.catalog,
        "schema": config.schema,
        "definition_sha256": definition_sha,
        "dataset_preflight_query_id": query_id,
        "data_quality_preflight_query_id": quality_query_id,
        "dataset_rows": len(rows),
        "dataset_requests": sum(int(row[3]) for row in rows),
        "dataset_zero_filled_days": sum(int(row[4]) for row in rows),
        "data_quality_rows": len(quality_observed),
        "data_quality_populations": [
            {"snapshot_id": key[0], "data_kind": key[1], "values": list(values)}
            for key, values in sorted(quality_observed.items())
        ],
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
    try:
        client.lakeview.get_published(dashboard.dashboard_id)
    except NotFound:
        pass
    else:
        raise ValueError(f"Dashboard has a published version; ID {dashboard.dashboard_id}")
    EXPORTED.parent.mkdir(parents=True, exist_ok=True)
    EXPORTED.write_bytes(exported_bytes)
    evidence["status"] = "draft_verified"
    evidence["export_sha256"] = hashlib.sha256(exported_bytes).hexdigest()
    evidence["export_artifact"] = str(EXPORTED.relative_to(ROOT)).replace("\\", "/")
    evidence["published_status_verified"] = True
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
