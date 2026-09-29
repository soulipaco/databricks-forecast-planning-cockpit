import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path("scripts").resolve()))
from deploy_development_diagnostics import check_rows, check_score_rows, render_definition
from deploy_readiness_dashboard import canonical_definition

RUN_ID = "development-two-model-012345abcdef"


def test_partial_development_template_is_explicit_and_unresolved_until_rendered():
    template = json.loads(
        Path("dashboards/development_diagnostics.template.lvdash.json").read_text(encoding="utf-8")
    )
    assert [page["name"] for page in template["pages"]] == ["readiness", "development_diagnostics"]
    content, rendered, queries = render_definition(RUN_ID)
    query = queries["development_diagnostics"]
    score_query = queries["development_paired_scores"]
    assert "{{development_run_id}}" not in content
    assert query.count(RUN_ID) == 3
    assert "partial_two_model_development_not_benchmark" in query
    assert "complete_two_model_development" in query
    assert "forecast_attempts" in query and "evaluation_cells" in query
    assert "ai_forecast(" not in query.lower()
    assert "HAVING COUNT(DISTINCT model_id) = 2" in score_query
    assert "SUM(c.abs_error_sum) / NULLIF(SUM(c.actual_sum), 0)" in score_query
    assert "2024-10-31" in score_query and "2024-11-30" in score_query
    assert "partial_two_model_development_not_benchmark" in score_query
    labels = " ".join(
        "".join(widget["widget"].get("multilineTextboxSpec", {}).get("lines", []))
        for widget in rendered["pages"][1]["layout"]
    )
    assert "not a three-model leaderboard" in labels
    assert "2025 evaluation" in labels
    assert "capacity evidence" in labels
    tables = {entry["widget"]["name"]: entry["widget"] for entry in rendered["pages"][1]["layout"]}
    assert tables["paired_score_table"]["queries"][0]["query"]["datasetName"] == "development_paired_scores"


def test_cell_preflight_rejects_missing_or_inconsistent_population():
    rows = [
        [RUN_ID, "partial_two_model_development_not_benchmark", origin, model, "21", "20", "1"]
        for origin in ("2024-10-31", "2024-11-30")
        for model in ("snaive7", "prophet_tuned")
    ]
    assert sum(item["expected_cells"] for item in check_rows(rows, RUN_ID)) == 84
    with pytest.raises(ValueError, match="four origin/model"):
        check_rows(rows[:-1], RUN_ID)
    rows[0][5] = "22"
    with pytest.raises(ValueError, match="do not reconcile"):
        check_rows(rows, RUN_ID)


def test_paired_score_preflight_reconciles_with_saved_evidence():
    score = json.loads(Path("evidence/workspace_development_score_reconcile_20260929.json").read_text(encoding="utf-8"))
    diagnostic = json.loads(Path("evidence/development_two_model_diagnostic_20260929.json").read_text(encoding="utf-8"))
    run_id = score["run_id"]
    rows = [
        [run_id, "partial_two_model_development_not_benchmark", model, "42",
         str(values["abs_error_sum"]), str(values["actual_sum"]),
         str(values["abs_error_sum"] / values["actual_sum"])]
        for model, values in score["models"].items()
    ]
    assert len(check_score_rows(rows, run_id, score, diagnostic)) == 2
    rows[0][3] = "41"
    with pytest.raises(ValueError, match="paired count"):
        check_score_rows(rows, run_id, score, diagnostic)


def test_exported_draft_matches_rendered_template_and_remains_unpublished():
    evidence = json.loads(Path("evidence/workspace_dashboard_paired_scores_20260929.json").read_text(encoding="utf-8"))
    exported_bytes = Path("evidence/development_paired_scores_export_20260929.lvdash.json").read_bytes()
    content, rendered, _ = render_definition(evidence["run_id"])
    assert evidence["published"] is False and evidence["published_status_verified"] is True
    assert hashlib.sha256(content.encode("utf-8")).hexdigest() == evidence["definition_sha256"]
    assert hashlib.sha256(exported_bytes).hexdigest() == evidence["export_sha256"]
    assert canonical_definition(json.loads(exported_bytes)) == canonical_definition(rendered)
