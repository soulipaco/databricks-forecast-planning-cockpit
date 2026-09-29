"""Build, deploy and verify the final benchmark AI/BI dashboard from persisted Delta tables.

Every dataset binds the frozen final run ID and reads stored rows only; no model is invoked.
The definition is written to dashboards/ so the deployed dashboard stays code-managed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.dashboards import Dashboard
from deploy_readiness_dashboard import canonical_definition
from verify_workspace_silver import ROOT, run_query

from nyc311_forecast.config import load_config
from nyc311_forecast.platform.persist_final import RUN_ID

DEFINITION = ROOT / "dashboards/final_benchmark.lvdash.json"
DISPLAY_NAME = "NYC 311 forecast benchmark: 2025 results"
PAIRED = (
    "paired AS (SELECT series_id, origin FROM evaluation_cells WHERE run_id = '{run}' "
    "AND paired_status = 'complete' GROUP BY series_id, origin "
    "HAVING COUNT(DISTINCT model_id) = 3), "
    "cells AS (SELECT ec.* FROM evaluation_cells ec JOIN paired p "
    "ON p.series_id = ec.series_id AND p.origin = ec.origin WHERE ec.run_id = '{run}')"
)
LABEL = (
    "CASE model_id WHEN 'ai_forecast_v2' THEN 'Databricks ai_forecast v2' "
    "WHEN 'prophet_tuned' THEN 'Tuned Prophet' ELSE 'Weekly seasonal naive' END"
)


def datasets(run: str, featured: str) -> list[dict]:
    leaderboard = (ROOT / "sql/final_leaderboard.sql").read_text(encoding="utf-8")
    leaderboard = "\n".join(
        line for line in leaderboard.splitlines() if not line.startswith("--")
    ).replace(":run_id", f"'{run}'")
    return [
        {"name": "leaderboard", "displayName": "Paired leaderboard",
         "queryLines": [(f"SELECT {LABEL} AS model, * FROM ({leaderboard}) ORDER BY median_series_wape")]},
        {"name": "series_wape", "displayName": "Series WAPE by model",
         "queryLines": [(f"WITH {PAIRED.format(run=run)} SELECT series_id, {LABEL} AS model, "
                        "SUM(abs_error_sum) / SUM(actual_sum) AS wape FROM cells "
                        "GROUP BY series_id, model_id ORDER BY series_id, model")]},
        {"name": "origin_wape", "displayName": "Pooled WAPE by forecast origin",
         "queryLines": [(f"WITH {PAIRED.format(run=run)} SELECT origin, {LABEL} AS model, "
                        "SUM(abs_error_sum) / SUM(actual_sum) AS wape, "
                        "SUM(signed_error_sum) / SUM(actual_sum) AS signed_bias "
                        "FROM cells GROUP BY origin, model_id ORDER BY origin, model")]},
        {"name": "run_health", "displayName": "Run health",
         "queryLines": [(f"SELECT {LABEL} AS model, COUNT(*) AS attempts, "
                        "SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successful, "
                        "SUM(CASE WHEN status <> 'success' THEN 1 ELSE 0 END) AS failed, "
                        "percentile_cont(0.5) WITHIN GROUP (ORDER BY wall_seconds) "
                        "AS median_wall_seconds, "
                        "percentile_cont(0.5) WITHIN GROUP (ORDER BY compute_seconds) "
                        "AS median_warehouse_seconds "
                        f"FROM forecast_attempts WHERE run_id = '{run}' GROUP BY model_id "
                        "ORDER BY model")]},
        {"name": "featured_forecast", "displayName": "Featured series, final origin",
         "queryLines": [(f"SELECT ds, {LABEL} AS model, prediction AS requests FROM "
                        f"forecast_values WHERE run_id = '{run}' AND series_id = '{featured}' "
                        "AND origin = DATE '2025-11-30' UNION ALL "
                        "SELECT fv.ds, 'Actual requests' AS model, CAST(dr.y AS DOUBLE) "
                        "FROM forecast_values fv JOIN forecast_runs fr ON fr.run_id = fv.run_id "
                        "JOIN daily_requests dr ON dr.snapshot_id = fr.snapshot_id "
                        "AND dr.series_id = fv.series_id AND dr.ds = fv.ds "
                        f"WHERE fv.run_id = '{run}' AND fv.series_id = '{featured}' "
                        "AND fv.origin = DATE '2025-11-30' AND fv.model_id = 'snaive7' "
                        "ORDER BY ds, model")]},
    ]


def _fields(*names: str) -> list[dict]:
    return [{"name": n, "expression": f"`{n}`"} for n in names]


def _widget(name, dataset, fields, spec, x, y, w, h):
    return {"widget": {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": dataset, "fields": _fields(*fields), "disaggregated": True}}],
        "spec": spec}, "position": {"x": x, "y": y, "width": w, "height": h}}


def _text(name, lines, y, h):
    return {"widget": {"name": name, "multilineTextboxSpec": {"lines": lines}},
            "position": {"x": 0, "y": y, "width": 6, "height": h}}


def _chart(kind, x, y, color, title, x_type="categorical", y_format=None):
    y_enc = {"fieldName": y[0], "scale": {"type": "quantitative"}, "displayName": y[1]}
    if y_format:
        y_enc["format"] = y_format
    return {"version": 3, "widgetType": kind, "encodings": {
        "x": {"fieldName": x[0], "scale": {"type": x_type}, "displayName": x[1]},
        "y": y_enc,
        "color": {"fieldName": color, "scale": {"type": "categorical"}, "displayName": "Model"}},
        "frame": {"showTitle": True, "title": title}}


def build(run: str, featured: str, summary: dict) -> dict:
    pct = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 1}}
    m = summary["models"]
    headline = (
        f"**ai_forecast v2 had the lowest error** (median series WAPE "
        f"{m['ai_forecast_v2']['primary_median_series_wape']:.1%} vs Prophet "
        f"{m['prophet_tuned']['primary_median_series_wape']:.1%}, naive "
        f"{m['snaive7']['primary_median_series_wape']:.1%}) **but under-forecast by "
        f"{-m['ai_forecast_v2']['paired_signed_bias']:.1%} of volume**, so it fails the "
        "pre-registered practically-competitive rule."
    )
    table_cols = [("model", "Model"), ("median_series_wape", "Median series WAPE (primary)"),
                  ("pooled_wape", "Pooled WAPE"), ("signed_bias", "Signed bias"),
                  ("interval_coverage", "80% interval coverage"), ("paired_cells", "Paired cells")]
    layout = [
        _text("title", ["# NYC 311 daily requests: 2025 forecast benchmark"], 0, 1),
        _text("headline", [headline], 1, 2),
        _widget("leaderboard_table", "leaderboard", [c for c, _ in table_cols], {
            "version": 2, "widgetType": "table",
            "encodings": {"columns": [{"fieldName": c, "displayName": d} for c, d in table_cols]},
            "frame": {"showTitle": True,
                      "title": "Leaderboard on 252 paired series-origins (lower WAPE is better)"}},
            0, 3, 6, 4),
        _widget("series_chart", "series_wape", ["series_id", "wape", "model"],
                _chart("bar", ("series_id", "Series"), ("wape", "WAPE"), "model",
                       "WAPE by series, 12 origins pooled", y_format=pct), 0, 7, 6, 8),
        _widget("origin_chart", "origin_wape", ["origin", "wape", "model"],
                _chart("line", ("origin", "Forecast origin"), ("wape", "Pooled WAPE"), "model",
                       "Pooled WAPE by monthly origin", x_type="temporal", y_format=pct),
                0, 15, 3, 6),
        _widget("bias_chart", "origin_wape", ["origin", "signed_bias", "model"],
                _chart("line", ("origin", "Forecast origin"), ("signed_bias", "Signed bias"),
                       "model", "Signed bias by origin (negative = under-forecast)",
                       x_type="temporal", y_format=pct), 3, 15, 3, 6),
        _widget("featured_chart", "featured_forecast", ["ds", "requests", "model"],
                _chart("line", ("ds", "Date"), ("requests", "Daily requests"), "model",
                       f"{featured}: forecasts from 2025-11-30 vs actual", x_type="temporal"),
                0, 21, 6, 6),
        _widget("health_table", "run_health",
                ["model", "attempts", "successful", "failed", "median_wall_seconds",
                 "median_warehouse_seconds"], {
                    "version": 2, "widgetType": "table", "encodings": {"columns": [
                        {"fieldName": "model", "displayName": "Model"},
                        {"fieldName": "attempts", "displayName": "Attempts"},
                        {"fieldName": "successful", "displayName": "Successful"},
                        {"fieldName": "failed", "displayName": "Failed"},
                        {"fieldName": "median_wall_seconds", "displayName": "Median wall s"},
                        {"fieldName": "median_warehouse_seconds",
                         "displayName": "Median warehouse s (v2 only)"}]},
                    "frame": {"showTitle": True, "title": "Run health (all attempts retained)"}},
                0, 27, 6, 4),
        _text("method", [(
            "Method: 21 borough × problem-family series, 1,095-day history per origin, twelve "
            "month-end origins from 2024-12-31 to 2025-11-30, 28-day horizon. Protocol frozen "
            "before any 2025 data was retrieved. Prophet and naive ran locally; v2 in a "
            "serverless SQL warehouse. Runtime is not like-for-like. Retrospective backtest; "
            f"v2 pretraining corpus unknown. Run `{run}`. The dashboard reads stored results "
            "only and never refits a model.")], 31, 3),
    ]
    return {"datasets": datasets(run, featured),
            "pages": [{"name": "results", "displayName": "2025 results",
                       "pageType": "PAGE_TYPE_CANVAS", "layout": layout}]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--persistence-evidence", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--release-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--export", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.output, args.export):
        if path.exists():
            raise ValueError(f"{path} exists; preserve prior evidence")
    persisted = json.loads(args.persistence_evidence.read_text(encoding="utf-8"))
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    run = persisted["run_id"]
    if (not RUN_ID.fullmatch(run) or persisted["status"] != "verified_final_three_model_persisted"
            or summary["run_id"] != run):
        raise ValueError("Dashboard requires the verified persisted final run")
    featured = json.loads(args.release_manifest.read_text(encoding="utf-8"))[
        "featured_series"]["median_native_minus_prophet"]
    definition = build(run, featured, summary)
    if any("ai_forecast(" in "".join(d["queryLines"]).lower() for d in definition["datasets"]):
        raise ValueError("Dashboard must read persisted tables only")
    content = json.dumps(definition, indent=2, ensure_ascii=False) + "\n"
    DEFINITION.write_text(content, encoding="utf-8")
    config = load_config(args.config)
    client = WorkspaceClient(profile=config.workspace_profile)
    if client.config.host.rstrip("/") != config.workspace_host.rstrip("/"):
        raise ValueError("Authenticated workspace host differs from config")
    checks = {}
    for dataset in definition["datasets"]:
        sql = dataset["queryLines"][0]
        sql = re.sub(
            r"\b(FROM|JOIN)\s+(evaluation_cells|forecast_attempts|forecast_values|"
            r"forecast_runs|daily_requests)\b",
            rf"\1 {config.catalog}.{config.schema}.\2", sql,
        )
        query_id, rows = run_query(client.statement_execution, config.warehouse_id, sql)
        checks[dataset["name"]] = {"query_id": query_id, "rows": len(rows or [])}
        if dataset["name"] == "leaderboard":
            got = {r[1]: float(r[2]) for r in rows}
            for model, stats in summary["models"].items():
                if not math.isclose(got[model], stats["primary_median_series_wape"],
                                    rel_tol=1e-9):
                    raise ValueError(f"Dashboard leaderboard differs for {model}")
    expected_rows = {"leaderboard": 3, "series_wape": 63, "origin_wape": 36,
                     "run_health": 3, "featured_forecast": 112}
    if {k: v["rows"] for k, v in checks.items()} != expected_rows:
        raise ValueError(f"Dashboard dataset populations differ: {checks}")
    dashboard = client.lakeview.create(
        Dashboard(display_name=DISPLAY_NAME, warehouse_id=config.warehouse_id,
                  serialized_dashboard=content),
        dataset_catalog=config.catalog, dataset_schema=config.schema,
    )
    stored = client.lakeview.get(dashboard.dashboard_id)
    exported = json.loads(stored.serialized_dashboard)
    if canonical_definition(exported) != canonical_definition(definition):
        raise ValueError("Stored dashboard definition differs from the repository definition")
    args.export.write_text(json.dumps(exported, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    evidence = {
        "status": "final_dashboard_draft_api_verified", "run_id": run,
        "dashboard_id": dashboard.dashboard_id, "display_name": DISPLAY_NAME,
        "definition": str(DEFINITION.relative_to(ROOT)),
        "definition_sha256": hashlib.sha256(DEFINITION.read_bytes()).hexdigest(),
        "export_sha256": hashlib.sha256(args.export.read_bytes()).hexdigest(),
        "dataset_checks": checks, "published": False,
        "workspace": "trial workspace; host kept out of public evidence",
    }
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
