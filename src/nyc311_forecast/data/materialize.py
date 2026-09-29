"""Build a development-only daily Silver spine from two verified source snapshots."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

from nyc311_forecast.data.series import daily_spine, normalize
from nyc311_forecast.ingest.snapshot import digest


def _read_snapshot(root: Path, expected_start: str, expected_end: str) -> tuple[list[dict], set[str], str]:
    source = json.loads((root / "data_source_manifest.json").read_text(encoding="utf-8"))
    summary_path = root / "snapshot_manifest.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if (source["range_start"], source["range_end"]) != (expected_start, expected_end):
        raise ValueError("Source snapshot has wrong date range")
    if summary["status"] != "complete":
        raise ValueError("Source snapshot is incomplete")
    first_year, first_month = map(int, expected_start[:7].split("-"))
    end_year, end_month = map(int, expected_end[:7].split("-"))
    expected_months = []
    year, month = first_year, first_month
    while (year, month) < (end_year, end_month):
        expected_months.append(f"{year}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    if summary["partition_ids"] != expected_months:
        raise ValueError("Source snapshot lacks expected monthly coverage")
    rows: list[dict] = []
    months = set(summary["partition_ids"])
    total = 0
    for month in summary["partition_ids"]:
        base = root / "partitions" / month
        partition = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
        payload = json.loads((base / "aggregates.json").read_text(encoding="utf-8"))
        if partition["status"] != "complete" or digest(payload) != partition["payload_hash"]:
            raise ValueError(f"Corrupt source partition: {month}")
        if partition["source_count"] != partition["grouped_count"]:
            raise ValueError(f"Unreconciled source partition: {month}")
        total += partition["source_count"]
        rows.extend(payload)
    if total != summary["source_count"]:
        raise ValueError("Source snapshot total differs from partitions")
    return rows, months, hashlib.sha256(summary_path.read_bytes()).hexdigest()


def materialize_development(
    selection_snapshot: Path,
    development_snapshot: Path,
    series_manifest: Path,
    output_dir: Path,
    *,
    snapshot_id: str,
) -> Path:
    """Write 2021–2024 daily requests; 2025 data cannot enter this path."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", snapshot_id):
        raise ValueError("Invalid Silver snapshot ID")
    selection_rows, selection_months, selection_hash = _read_snapshot(
        Path(selection_snapshot), "2021-01-01", "2024-01-01"
    )
    development_rows, development_months, development_hash = _read_snapshot(
        Path(development_snapshot), "2024-01-01", "2025-01-01"
    )
    manifest_path = Path(series_manifest)
    selection = json.loads(manifest_path.read_text(encoding="utf-8"))
    if selection["selection_data_hash"] != selection_hash:
        raise ValueError("Series selection hash differs from source snapshot")
    counts, excluded = normalize(selection_rows + development_rows)
    spine = daily_spine(
        counts, selection["candidates"], date(2021, 1, 1), date(2025, 1, 1),
        selection_months | development_months,
    )
    expected = sum(row["selected"] for row in selection["candidates"]) * 1461
    if len(spine) != expected or any(row["y"] is None for row in spine):
        raise ValueError("Development daily spine is incomplete")
    lineage = {
        "snapshot_id": snapshot_id,
        "selection_source_id": selection["snapshot_id"],
        "selection_source_hash": selection_hash,
        "development_source_id": json.loads((Path(development_snapshot) / "snapshot_manifest.json").read_text())["snapshot_id"],
        "development_source_hash": development_hash,
        "series_manifest_hash": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }
    return _write_silver(Path(output_dir), snapshot_id, spine, selection, lineage, excluded)


def materialize_evaluation(
    selection_snapshot: Path,
    development_snapshot: Path,
    evaluation_snapshot: Path,
    series_manifest: Path,
    freeze_manifest: Path,
    output_dir: Path,
    *,
    snapshot_id: str,
) -> Path:
    """Write 2021–2025 daily requests for the final evaluation; requires a frozen protocol."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", snapshot_id):
        raise ValueError("Invalid Silver snapshot ID")
    freeze = json.loads(Path(freeze_manifest).read_text(encoding="utf-8"))
    manifest_path = Path(series_manifest)
    if freeze.get("status") != "frozen" or freeze["hashes"]["series_manifest"] != hashlib.sha256(
        manifest_path.read_bytes()
    ).hexdigest():
        raise ValueError("2025 Silver requires the frozen protocol and its series manifest")
    selection_rows, selection_months, selection_hash = _read_snapshot(
        Path(selection_snapshot), "2021-01-01", "2024-01-01"
    )
    development_rows, development_months, development_hash = _read_snapshot(
        Path(development_snapshot), "2024-01-01", "2025-01-01"
    )
    evaluation_rows, evaluation_months, evaluation_hash = _read_snapshot(
        Path(evaluation_snapshot), "2025-01-01", "2026-01-01"
    )
    selection = json.loads(manifest_path.read_text(encoding="utf-8"))
    if selection["selection_data_hash"] != selection_hash:
        raise ValueError("Series selection hash differs from source snapshot")
    counts, excluded = normalize(selection_rows + development_rows + evaluation_rows)
    spine = daily_spine(
        counts, selection["candidates"], date(2021, 1, 1), date(2026, 1, 1),
        selection_months | development_months | evaluation_months,
    )
    expected = sum(row["selected"] for row in selection["candidates"]) * 1826
    if len(spine) != expected or any(row["y"] is None for row in spine):
        raise ValueError("Evaluation daily spine is incomplete")
    lineage = {
        "snapshot_id": snapshot_id,
        "selection_source_id": selection["snapshot_id"],
        "selection_source_hash": selection_hash,
        "development_source_id": json.loads((Path(development_snapshot) / "snapshot_manifest.json").read_text())["snapshot_id"],
        "development_source_hash": development_hash,
        "evaluation_source_id": json.loads((Path(evaluation_snapshot) / "snapshot_manifest.json").read_text())["snapshot_id"],
        "evaluation_source_hash": evaluation_hash,
        "series_manifest_hash": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "freeze_manifest_hash": hashlib.sha256(Path(freeze_manifest).read_bytes()).hexdigest(),
    }
    return _write_silver(Path(output_dir), snapshot_id, spine, selection, lineage, excluded)


def _write_silver(
    output_dir: Path, snapshot_id: str, spine: list[dict], selection: dict,
    lineage: dict, excluded: dict,
) -> Path:
    output = output_dir / snapshot_id
    output.mkdir(parents=True, exist_ok=True)
    lines = []
    for row in spine:
        lines.append(json.dumps({
            "snapshot_id": snapshot_id, "series_id": row["series_id"],
            "ds": row["ds"].isoformat(), "borough": row["borough"],
            "problem_family": row["problem_family"], "y": row["y"],
            "is_zero_filled": row["is_zero_filled"], "quality_status": row["quality_status"],
            "mapping_version": selection["mapping_version"],
        }, sort_keys=True, ensure_ascii=False))
    content = ("\n".join(lines) + "\n").encode()
    lineage = {
        **lineage,
        "mapping_version": selection["mapping_version"],
        "row_count": len(spine),
        "zero_filled_rows": sum(row["is_zero_filled"] for row in spine),
        "excluded_request_counts": dict(sorted(excluded.items())),
        "daily_payload_hash": hashlib.sha256(content).hexdigest(),
        "status": "complete",
    }
    payload_path = output / "daily_requests.jsonl"
    lineage_path = output / "manifest.json"
    if payload_path.exists() and payload_path.read_bytes() != content:
        raise ValueError("Existing Silver payload differs; use a new snapshot ID")
    if lineage_path.exists() and json.loads(lineage_path.read_text(encoding="utf-8")) != lineage:
        raise ValueError("Existing Silver manifest differs; use a new snapshot ID")
    if lineage_path.exists() and not payload_path.exists():
        raise ValueError("Silver manifest exists without payload")
    if not payload_path.exists():
        staged = output / "daily_requests.jsonl.tmp"
        staged.write_bytes(content)
        staged.replace(payload_path)
    if not lineage_path.exists():
        staged = output / "manifest.json.tmp"
        staged.write_text(json.dumps(lineage, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        staged.replace(lineage_path)
    return output
