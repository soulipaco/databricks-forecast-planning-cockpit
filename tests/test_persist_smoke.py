import copy
import json
from pathlib import Path

import pytest

from nyc311_forecast.platform.persist_smoke import stage, transform

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evidence/development_slice_20260929.json"


def test_smoke_stage_preserves_grid_and_labels(tmp_path):
    manifest = stage(SOURCE, tmp_path / "smoke-stage")
    assert manifest["status"] == "smoke_only_not_benchmark"
    assert {name: info["rows"] for name, info in manifest["tables"].items()} == {
        "forecast_runs": 1, "forecast_attempts": 12,
        "forecast_values": 336, "evaluation_cells": 12}
    runs = [json.loads(line) for line in (tmp_path / "smoke-stage/forecast_runs.jsonl").read_text().splitlines()]
    assert runs[0]["status"] == "smoke_only_not_benchmark"
    values = [json.loads(line) for line in (tmp_path / "smoke-stage/forecast_values.jsonl").read_text().splitlines()]
    assert {row["model_id"] for row in values} == {"snaive7", "prophet_fixed_smoke"}
    assert all(not row["is_fallback"] for row in values)
    assert stage(SOURCE, tmp_path / "smoke-stage") == manifest


def test_stage_rejects_incomplete_grid_and_date_mismatch():
    source = json.loads(SOURCE.read_text())
    incomplete = copy.deepcopy(source)
    incomplete["forecast_values"].pop()
    with pytest.raises(ValueError, match="row counts"):
        transform(incomplete)
    wrong_date = copy.deepcopy(source)
    wrong_date["forecast_values"][0]["ds"] = "2024-11-02"
    with pytest.raises(ValueError, match="date/lead"):
        transform(wrong_date)
    benchmark_claim = copy.deepcopy(source)
    benchmark_claim["status"] = "complete"
    with pytest.raises(ValueError, match="labeled"):
        transform(benchmark_claim)


def test_stage_detects_existing_conflicting_file(tmp_path):
    target = tmp_path / "smoke-stage"
    stage(SOURCE, target)
    (target / "forecast_values.jsonl").write_text("corrupted")
    with pytest.raises(ValueError, match="Existing stage differs"):
        stage(SOURCE, target)
