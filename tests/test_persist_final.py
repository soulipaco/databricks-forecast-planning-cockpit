"""Final persistence transform on the real committed benchmark artifact."""

import json
from pathlib import Path

import pytest

from nyc311_forecast.platform.persist_final import transform

SOURCE = Path(__file__).resolve().parents[1] / "evidence/final_three_model_20260929.json"


def test_final_artifact_maps_to_complete_contract_rows():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows, summary = transform(source, protocol_hash="p", config_hash="c")
    assert summary == {"expected_cells": 756, "complete_cells": 756, "failed_cells": 0}
    assert len(rows["forecast_values"]) == 756 * 28
    assert {r["run_id"] for table in rows.values() for r in table} == {source["run_id"]}
    native = [a for a in rows["forecast_attempts"] if a["model_id"] == "ai_forecast_v2"]
    assert all(a["query_id"] and a["compute_seconds"] is not None for a in native)


def test_missing_cell_or_foreign_status_is_rejected():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    with pytest.raises(ValueError):
        transform({**source, "status": "partial_two_model_development_not_benchmark"},
                  protocol_hash="p", config_hash="c")
    with pytest.raises(ValueError, match="Incomplete"):
        transform({**source, "evaluation_cells": source["evaluation_cells"][1:]},
                  protocol_hash="p", config_hash="c")
