"""Freeze series choices from a complete 2021–2023 snapshot only."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from nyc311_forecast.data.series import normalize, select_series
from nyc311_forecast.ingest.snapshot import digest


def select_from_snapshot(
    snapshot_dir: Path,
    experiment_id: str,
    output_file: Path,
    *,
    expected_snapshot_id: str | None = None,
) -> Path:
    root = Path(snapshot_dir)
    source = json.loads((root / "data_source_manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((root / "snapshot_manifest.json").read_text(encoding="utf-8"))
    if expected_snapshot_id is not None and summary["snapshot_id"] != expected_snapshot_id:
        raise ValueError("Snapshot ID differs from config")
    if source["range_start"] != "2021-01-01" or source["range_end"] != "2024-01-01":
        raise ValueError("Selection requires exactly the 2021–2023 snapshot")
    expected = [f"{year}-{month:02d}" for year in range(2021, 2024) for month in range(1, 13)]
    if summary["status"] != "complete" or summary["partition_ids"] != expected:
        raise ValueError("Selection snapshot lacks complete monthly coverage")
    rows: list[dict] = []
    for partition_id in expected:
        base = root / "partitions" / partition_id
        manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
        if manifest["status"] != "complete":
            raise ValueError(f"Incomplete partition: {partition_id}")
        payload = json.loads((base / "aggregates.json").read_text(encoding="utf-8"))
        if digest(payload) != manifest["payload_hash"]:
            raise ValueError(f"Payload hash mismatch: {partition_id}")
        rows.extend(payload)
    counts, excluded = normalize(rows)
    candidates = select_series(counts, date(2021, 1, 1), date(2024, 1, 1))
    snapshot_hash = hashlib.sha256((root / "snapshot_manifest.json").read_bytes()).hexdigest()
    result = {
        "experiment_id": experiment_id,
        "snapshot_id": summary["snapshot_id"],
        "selection_data_hash": snapshot_hash,
        "mapping_version": "exact-complaint-type-v1",
        "mapping_hash": hashlib.sha256(b"{}\n").hexdigest(),
        "unknown_borough_request_counts": dict(sorted(excluded.items())),
        "candidates": candidates,
    }
    output = Path(output_file)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        if json.loads(output.read_text(encoding="utf-8")) != result:
            raise ValueError("Frozen series manifest differs; choose a new output path")
    else:
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
