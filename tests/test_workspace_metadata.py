import hashlib
import json
from pathlib import Path


def test_staged_workspace_lineage_has_complete_unique_development_keys():
    root = Path("data/workspace_stage/development-metadata-20260929")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    partitions = [
        json.loads(line) for line in (root / "source_partitions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    series = [
        json.loads(line) for line in (root / "series_manifest.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(partitions) == 48
    assert len({(row["snapshot_id"], row["partition_id"]) for row in partitions}) == 48
    assert all(row["status"] == "complete" and row["source_count"] == row["grouped_count"]
               for row in partitions)
    assert len(series) == 1245
    assert len({(row["experiment_id"], row["series_id"]) for row in series}) == 1245
    assert sum(row["inclusion_status"] == "selected" for row in series) == 21
    assert all(row["selection_rank"] is None for row in series if row["inclusion_status"] != "selected")
    for name in ("source_partitions", "series_manifest"):
        assert hashlib.sha256((root / f"{name}.jsonl").read_bytes()).hexdigest() == manifest[f"{name}_sha256"]
