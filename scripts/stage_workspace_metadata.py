"""Build verified JSONL payloads for workspace source and series lineage tables."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ROOT / "data/snapshots/selection-2021-2023-20260929",
    ROOT / "data/snapshots/development-2024-20260929",
)
SELECTION = ROOT / "data/series_manifest/selection-v1.json"
OUTPUT = ROOT / "data/workspace_stage/development-metadata-20260929"


def read_source_partitions() -> list[dict]:
    rows = []
    for snapshot_dir, expected_count in zip(SOURCES, (36, 12)):
        snapshot = json.loads((snapshot_dir / "snapshot_manifest.json").read_text(encoding="utf-8"))
        if snapshot["status"] != "complete" or len(snapshot["partition_ids"]) != expected_count:
            raise ValueError(f"Incomplete snapshot: {snapshot_dir.name}")
        for partition_id in snapshot["partition_ids"]:
            path = snapshot_dir / "partitions" / partition_id / "manifest.json"
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != snapshot["partition_manifest_hashes"][partition_id]:
                raise ValueError(f"Partition manifest hash mismatch: {partition_id}")
            part = json.loads(path.read_text(encoding="utf-8"))
            if (part["snapshot_id"], part["partition_id"], part["status"]) != (
                snapshot["snapshot_id"],
                partition_id,
                "complete",
            ) or part["source_count"] != part["grouped_count"]:
                raise ValueError(f"Unreconciled partition: {partition_id}")
            rows.append(
                {
                    key: part[key]
                    for key in (
                        "snapshot_id",
                        "partition_id",
                        "endpoint",
                        "query_hash",
                        "extracted_at",
                        "payload_hash",
                        "aggregate_rows",
                        "source_count",
                        "grouped_count",
                        "status",
                    )
                }
            )
    if len(rows) != 48 or len({(row["snapshot_id"], row["partition_id"]) for row in rows}) != 48:
        raise ValueError("Expected 48 unique source partitions")
    return rows


def read_series_manifest() -> list[dict]:
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    if selection["snapshot_id"] != "selection-2021-2023-20260929":
        raise ValueError("Unexpected series selection source")
    rows = [
        {
            "experiment_id": selection["experiment_id"],
            "series_id": candidate["series_id"],
            "selection_rank": candidate["family_rank"] if candidate["selected"] else None,
            "inclusion_status": "selected" if candidate["selected"] else "excluded",
            "reason": candidate["reason"],
            "positive_days": candidate["positive_days"],
            "median_daily_count": candidate["median_daily_count"],
            "active_span_days": candidate["active_span_days"],
            "selection_data_hash": selection["selection_data_hash"],
            "mapping_hash": selection["mapping_hash"],
        }
        for candidate in selection["candidates"]
    ]
    if len(rows) != 1245 or len({(row["experiment_id"], row["series_id"]) for row in rows}) != 1245:
        raise ValueError("Expected 1,245 unique candidate series")
    if sum(row["inclusion_status"] == "selected" for row in rows) != 21:
        raise ValueError("Expected 21 selected series")
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> str:
    content = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows)
    encoded = content.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise ValueError(f"Existing stage file differs: {path}")
    path.write_bytes(encoded)
    return digest


def main() -> None:
    source_rows = read_source_partitions()
    series_rows = read_series_manifest()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source_hash = write_jsonl(OUTPUT / "source_partitions.jsonl", source_rows)
    series_hash = write_jsonl(OUTPUT / "series_manifest.jsonl", series_rows)
    manifest = {
        "stage_id": OUTPUT.name,
        "source_partitions_rows": len(source_rows),
        "source_partitions_sha256": source_hash,
        "series_manifest_rows": len(series_rows),
        "selected_series_rows": 21,
        "series_manifest_sha256": series_hash,
        "selection_manifest_sha256": hashlib.sha256(SELECTION.read_bytes()).hexdigest(),
        "status": "complete",
    }
    path = OUTPUT / "manifest.json"
    content = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    path.write_bytes(content.encode("utf-8"))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
