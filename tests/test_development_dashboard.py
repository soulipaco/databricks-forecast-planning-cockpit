import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path("scripts").resolve()))
from deploy_development_diagnostics import check_rows, render_definition

RUN_ID = "development-two-model-012345abcdef"


def test_partial_development_template_is_explicit_and_unresolved_until_rendered():
    template = json.loads(
        Path("dashboards/development_diagnostics.template.lvdash.json").read_text(encoding="utf-8")
    )
    assert [page["name"] for page in template["pages"]] == ["readiness", "development_diagnostics"]
    content, rendered, query = render_definition(RUN_ID)
    assert "{{development_run_id}}" not in content
    assert query.count(RUN_ID) == 3
    assert "partial_two_model_development_not_benchmark" in query
    assert "complete_two_model_development" in query
    assert "forecast_attempts" in query and "evaluation_cells" in query
    assert "ai_forecast(" not in query.lower()
    labels = " ".join(
        "".join(widget["widget"].get("multilineTextboxSpec", {}).get("lines", []))
        for widget in rendered["pages"][1]["layout"]
    )
    assert "not a three-model leaderboard" in labels
    assert "2025 evaluation" in labels
    assert "capacity evidence" in labels


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
