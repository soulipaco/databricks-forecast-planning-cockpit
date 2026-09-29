"""Update an existing unpublished draft with verified 2024 two-model diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound
from databricks.sdk.service.dashboards import Dashboard
from deploy_readiness_dashboard import canonical_definition
from verify_workspace_silver import ROOT, run_query

from nyc311_forecast.config import load_config

TEMPLATE = ROOT / "dashboards/development_diagnostics.template.lvdash.json"
RUN_ID = re.compile(r"development-two-model-[a-f0-9]{12}\Z")
RUN_STATUS = "partial_two_model_development_not_benchmark"
EXPECTED_ROWS = {
    ("2024-10-31", "snaive7"),
    ("2024-10-31", "prophet_tuned"),
    ("2024-11-30", "snaive7"),
    ("2024-11-30", "prophet_tuned"),
}


def render_definition(run_id: str) -> tuple[str, dict, dict[str, str]]:
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("Expected a full two-model development run ID")
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count("{{development_run_id}}") != 4:
        raise ValueError("Run placeholder count changed")
    content = template.replace("{{development_run_id}}", run_id)
    definition = json.loads(content)
    if [page["name"] for page in definition["pages"]] != ["readiness", "development_diagnostics"]:
        raise ValueError("Unexpected dashboard pages")
    datasets = {dataset["name"]: dataset for dataset in definition["datasets"]}
    if set(datasets) != {"development_series", "data_quality", "development_diagnostics", "development_paired_scores"}:
        raise ValueError("Unexpected dashboard datasets")
    queries = {name: "".join(dataset["queryLines"]) for name, dataset in datasets.items()}
    if queries["development_diagnostics"].count(run_id) != 3 or queries["development_paired_scores"].count(run_id) != 1:
        raise ValueError("Development query is not scoped to the run and status")
    if any(RUN_STATUS not in queries[name] for name in ("development_diagnostics", "development_paired_scores")):
        raise ValueError("Development queries must guard run status")
    if "HAVING COUNT(DISTINCT model_id) = 2" not in queries["development_paired_scores"]:
        raise ValueError("Score query must use two-model paired cells")
    if any("ai_forecast(" in query.lower() for query in queries.values()):
        raise ValueError("Dashboard must read persisted tables only")
    return content, definition, queries


def check_rows(rows: list[list[str]] | None, run_id: str) -> list[dict]:
    if not rows or len(rows) != 4:
        raise ValueError("Expected four origin/model diagnostic rows")
    observed = []
    for row in rows:
        returned_run, status, origin, model_id = row[:4]
        expected, complete, incomplete = map(int, row[4:7])
        if returned_run != run_id or status != RUN_STATUS:
            raise ValueError("Wrong run or status in development dataset")
        if expected != 21 or complete < 0 or incomplete < 0 or complete + incomplete != expected:
            raise ValueError("Development cell counts do not reconcile")
        observed.append({"origin": origin, "model_id": model_id, "expected_cells": expected,
                         "complete_cells": complete, "incomplete_cells": incomplete})
    if {(row["origin"], row["model_id"]) for row in observed} != EXPECTED_ROWS:
        raise ValueError("Development dataset lacks an expected origin/model")
    return observed


def check_score_rows(rows: list[list[str]] | None, run_id: str, workspace_scores: dict,
                     diagnostic: dict) -> list[dict]:
    if not rows or len(rows) != 2:
        raise ValueError("Expected two paired score rows")
    if workspace_scores.get("run_id") != run_id or diagnostic.get("run_id") != run_id:
        raise ValueError("Score evidence run ID differs")
    if (workspace_scores.get("status") != "verified_two_model_development_scores_only" or
            diagnostic.get("status") != "two_model_2024_development_diagnostic_only" or
            diagnostic.get("complete_model_cells") != 84):
        raise ValueError("Score evidence is not the verified complete development diagnostic")
    if diagnostic.get("paired_series_origin_pairs") != 42:
        raise ValueError("Diagnostic evidence lacks 42 paired cells")
    if set(workspace_scores.get("models", {})) != {"snaive7", "prophet_tuned"}:
        raise ValueError("Workspace score evidence model set differs")
    observed = []
    for row in rows:
        returned_run, status, model = row[:3]
        cells = int(row[3])
        abs_error, actual_sum, pooled_wape = map(float, row[4:7])
        if returned_run != run_id or status != RUN_STATUS or cells != 42:
            raise ValueError("Score query run, status or paired count differs")
        if model not in workspace_scores["models"] or model not in diagnostic.get("models", {}):
            raise ValueError("Score query returned an unexpected model")
        reference = workspace_scores["models"][model]
        metric = diagnostic["models"][model]
        for actual, expected in (
            (cells, reference["cells"]),
            (abs_error, reference["abs_error_sum"]),
            (actual_sum, reference["actual_sum"]),
            (abs_error, metric["paired_abs_error_sum"]),
            (actual_sum, metric["paired_actual_sum"]),
            (pooled_wape, metric["paired_pooled_wape"]),
            (pooled_wape, abs_error / actual_sum),
        ):
            if not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-8):
                raise ValueError(f"Paired score differs from evidence for {model}")
        observed.append({"model_id": model, "paired_cells": cells,
                         "abs_error_sum": abs_error, "actual_sum": actual_sum,
                         "pooled_wape": pooled_wape})
    if {item["model_id"] for item in observed} != {"snaive7", "prophet_tuned"}:
        raise ValueError("Paired score rows are incomplete")
    if observed[0]["actual_sum"] != observed[1]["actual_sum"]:
        raise ValueError("Models do not share the paired actual denominator")
    return observed


def assert_unpublished(client: WorkspaceClient, dashboard_id: str) -> None:
    try:
        client.lakeview.get_published(dashboard_id)
    except NotFound:
        return
    raise ValueError(f"Dashboard has a published version; ID {dashboard_id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--persistence-evidence", type=Path, required=True)
    parser.add_argument("--score-evidence", type=Path, required=True)
    parser.add_argument("--diagnostic-evidence", type=Path, required=True)
    parser.add_argument("--prior-dashboard-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--export", type=Path, required=True)
    args = parser.parse_args()
    persisted = json.loads(args.persistence_evidence.read_text(encoding="utf-8"))
    run_id = persisted.get("run_id", "")
    if not RUN_ID.fullmatch(run_id) or persisted.get("status") != "verified_partial_two_model_development_not_benchmark":
        raise ValueError("Full development persistence evidence must be verified")
    if (persisted.get("expected_cells") != 84 or
            persisted.get("complete_cells", -1) + persisted.get("failed_cells", -1) != 84 or
            persisted.get("evaluation_cells_include_failures") is not True):
        raise ValueError("Persistence evidence has an incomplete development grid")
    result_tables = {item["table"].split(".")[-1]: item for item in persisted.get("results", [])}
    if set(result_tables) != {"forecast_runs", "forecast_attempts", "forecast_values", "evaluation_cells"}:
        raise ValueError("Persistence evidence lacks a contract table")
    if any(item["missing_rows"] or item["extra_rows"] or
           item["expected_rows"] != item["persisted_rows"] for item in result_tables.values()):
        raise ValueError("Persistence readback did not reconcile")
    prior = json.loads(args.prior_dashboard_evidence.read_text(encoding="utf-8"))
    if prior.get("published") is not False or not prior.get("dashboard_id"):
        raise ValueError("Only a recorded unpublished dashboard may be updated")
    workspace_scores = json.loads(args.score_evidence.read_text(encoding="utf-8"))
    diagnostic = json.loads(args.diagnostic_evidence.read_text(encoding="utf-8"))
    content, definition, queries = render_definition(run_id)
    definition_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    current = json.loads(args.output.read_text(encoding="utf-8")) if args.output.exists() else None
    if current and (current.get("definition_sha256") != definition_sha or current.get("dashboard_id") != prior["dashboard_id"]):
        raise ValueError("Existing evidence refers to a different draft or definition")
    config = load_config(args.config)
    if not all((config.workspace_host, config.workspace_profile, config.warehouse_id,
                config.catalog, config.schema)):
        raise ValueError("Workspace host, profile, warehouse, catalog and schema required")
    client = WorkspaceClient(profile=config.workspace_profile)
    if client.config.host.rstrip("/") != config.workspace_host.rstrip("/"):
        raise ValueError("Authenticated workspace host differs from config")
    def qualify(query: str) -> str:
        return re.sub(
            r"\b(FROM|JOIN) (forecast_attempts|evaluation_cells|forecast_runs)\b",
            lambda match: f"{match.group(1)} {config.catalog}.{config.schema}.{match.group(2)}",
            query,
        )

    query = qualify(queries["development_diagnostics"])
    query_id, rows = run_query(client.statement_execution, config.warehouse_id, query)
    observed = check_rows(rows, run_id)
    if sum(item["complete_cells"] for item in observed) != persisted["complete_cells"]:
        raise ValueError("Dashboard complete-cell count differs from persistence evidence")
    score_query_id, score_rows = run_query(
        client.statement_execution, config.warehouse_id,
        qualify(queries["development_paired_scores"]),
    )
    paired_scores = check_score_rows(score_rows, run_id, workspace_scores, diagnostic)
    existing = client.lakeview.get(prior["dashboard_id"])
    if existing.warehouse_id != config.warehouse_id:
        raise ValueError("Existing dashboard warehouse differs from config")
    assert_unpublished(client, prior["dashboard_id"])
    if not current:
        prior_export = ROOT / prior["export_artifact"]
        if hashlib.sha256(prior_export.read_bytes()).hexdigest() != prior["export_sha256"]:
            raise ValueError("Prior export hash differs from evidence")
        if canonical_definition(json.loads(existing.serialized_dashboard or "null")) != canonical_definition(json.loads(prior_export.read_text(encoding="utf-8"))):
            raise ValueError("Workspace draft differs from the prior verified export")
        client.lakeview.update(
            prior["dashboard_id"],
            Dashboard(display_name="NYC 311 Forecast Planning — Development Diagnostics",
                      warehouse_id=config.warehouse_id, serialized_dashboard=content),
            dataset_catalog=config.catalog,
            dataset_schema=config.schema,
        )
    retrieved = client.lakeview.get(prior["dashboard_id"])
    if canonical_definition(json.loads(retrieved.serialized_dashboard or "null")) != canonical_definition(definition):
        raise ValueError("Stored dashboard differs from rendered definition")
    if not retrieved.path or retrieved.warehouse_id != config.warehouse_id:
        raise ValueError("Stored dashboard path or warehouse differs")
    with client.workspace.download(retrieved.path) as stream:
        exported_bytes = stream.read()
    if canonical_definition(json.loads(exported_bytes.decode("utf-8"))) != canonical_definition(definition):
        raise ValueError("Workspace export differs from rendered definition")
    assert_unpublished(client, prior["dashboard_id"])
    args.export.parent.mkdir(parents=True, exist_ok=True)
    args.export.write_bytes(exported_bytes)
    evidence = {
        "status": "draft_verified_partial_two_model_development_with_scores",
        "dashboard_id": prior["dashboard_id"], "run_id": run_id,
        "run_status": RUN_STATUS, "dataset_query_id": query_id,
        "paired_score_query_id": score_query_id,
        "paired_score_rows": paired_scores,
        "dataset_rows": observed, "expected_cells": sum(x["expected_cells"] for x in observed),
        "complete_cells": sum(x["complete_cells"] for x in observed),
        "definition_sha256": definition_sha,
        "export_sha256": hashlib.sha256(exported_bytes).hexdigest(),
        "export_artifact": str(args.export.resolve().relative_to(ROOT)).replace("\\", "/"),
        "published": False, "published_status_verified": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
