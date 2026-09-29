import json
from pathlib import Path


def test_readiness_dashboard_binds_materialized_fields_and_labels_scope():
    definition = json.loads(
        Path("dashboards/development_readiness.lvdash.json").read_text(encoding="utf-8")
    )
    datasets = {dataset["name"]: dataset for dataset in definition["datasets"]}
    assert set(datasets) == {"development_series"}
    query = "".join(datasets["development_series"]["queryLines"])
    assert "FROM daily_requests " in query
    assert "development-silver-20260929" in query
    assert "ai_forecast(" not in query.lower()
    page = definition["pages"][0]
    assert page["pageType"] == "PAGE_TYPE_CANVAS"
    widgets = [entry["widget"] for entry in page["layout"]]
    labels = " ".join(
        "".join(widget.get("multilineTextboxSpec", {}).get("lines", [])) for widget in widgets
    )
    assert "no three-model benchmark" in labels
    assert "no 2025 evaluation results" in labels
    table = next(widget for widget in widgets if widget.get("spec", {}).get("widgetType") == "table")
    binding = table["queries"][0]["query"]
    assert binding["datasetName"] == "development_series"
    field_names = {field["name"] for field in binding["fields"]}
    column_names = {column["fieldName"] for column in table["spec"]["encodings"]["columns"]}
    assert field_names == column_names


def test_workspace_export_matches_tracked_readiness_definition():
    source = json.loads(
        Path("dashboards/development_readiness.lvdash.json").read_text(encoding="utf-8")
    )
    exported = json.loads(
        Path("evidence/development_readiness_export_20260929.lvdash.json").read_text(
            encoding="utf-8"
        )
    )
    assert exported["uiSettings"] == source["uiSettings"]
    assert exported["pages"][0]["name"] == source["pages"][0]["name"]
    assert exported["pages"][0]["layout"][-1] == source["pages"][0]["layout"][-1]
    assert len(exported["datasets"]) == 1
    assert exported["datasets"][0]["catalog"] == "mlops_dev"
    assert exported["datasets"][0]["schema"] == "nyc311_forecast"
    assert "".join(exported["datasets"][0]["queryLines"]) == "".join(
        source["datasets"][0]["queryLines"]
    )
