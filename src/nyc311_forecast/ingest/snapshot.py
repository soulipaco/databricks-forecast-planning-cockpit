"""Reconciled, immutable monthly source snapshots.

The payload is the returned aggregate JSON, not reconstructed request rows.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.error import HTTPError

from .client import DATASET, HOST, TRANSIENT, SocrataClient, SourceError, parse_count, retry_delay


def canonical_bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def digest(value) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def write_once(path: Path, value) -> None:
    content = canonical_bytes(value)
    if path.exists():
        if path.read_bytes() != content:
            raise SourceError(f"immutable artifact conflict: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(content)


def months(start: date, end: date):
    if start >= end or start.day != 1 or end.day != 1:
        raise ValueError("start/end must be ordered first-of-month dates")
    current = start
    while current < end:
        following = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
        yield current, following
        current = following


def validate_rows(rows: list[dict], start: date, end: date) -> int:
    seen = set()
    total = 0
    for row in rows:
        try:
            day = date.fromisoformat(row["request_date"][:10])
            borough = row["borough"]
            complaint = row["complaint_type"]
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceError("aggregate key invalid") from exc
        if not start <= day < end or not isinstance(borough, str) or not isinstance(complaint, str):
            raise SourceError("aggregate key outside partition or non-text")
        key = (day.isoformat(), borough, complaint)
        # Socrata text collation does not match Python's lexicographic order.
        # The query has a complete ORDER BY; validate uniqueness independently.
        if key in seen:
            raise SourceError("aggregate keys duplicate across pages")
        seen.add(key)
        total += parse_count(row.get("request_count"))
    return total


def extract_partition(client: SocrataClient, start: date, end: date, *, max_attempts=5):
    """Retry a complete partition on throttling, transient error or count drift."""
    where = client.where(start, end)
    query = {"where": where, "select": "date_trunc_ymd(created_date) AS request_date, borough, "
             "complaint_type, count(*) AS request_count", "group": "request_date, borough, complaint_type",
             "order": "request_date, borough, complaint_type", "api_version": client.version,
             "page_size": client.page_size}
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            before = client.source_count(start, end)
            rows = []
            page_count = 0
            while True:
                page = client.grouped_page(start, end, offset=len(rows), page_number=page_count + 1)
                page_count += 1
                rows.extend(page)
                if len(page) < client.page_size:
                    break
            grouped = validate_rows(rows, start, end)
            after = client.source_count(start, end)
            if before != after or grouped != after:
                raise SourceError(f"count drift: before={before}, grouped={grouped}, after={after}")
            return rows, {"partition_id": start.strftime("%Y-%m"), "start": start.isoformat(),
                          "end": end.isoformat(), "query": query, "query_hash": digest(query),
                          "aggregate_rows": len(rows), "source_count": after, "grouped_count": grouped,
                          "page_count": page_count, "payload_hash": digest(rows),
                          "status": "complete", "attempts": attempt}
        except HTTPError as exc:
            if exc.code not in TRANSIENT:
                raise SourceError(f"non-retryable HTTP {exc.code}") from exc
            last_error = SourceError(f"transient HTTP {exc.code}")
            delay = retry_delay(exc, attempt, client.rng)
        except SourceError as exc:
            last_error = exc
            delay = min(30, 2 ** (attempt - 1) + client.rng.uniform(0, 1))
        if attempt < max_attempts:
            client.sleeper(delay)
    raise SourceError(f"partition {start:%Y-%m} unstable after {max_attempts} attempts: {last_error}")


def extract_snapshot(start: date, end: date, output_dir: Path, snapshot_id: str,
                     *, client: SocrataClient | None = None, version: str = "soda2",
                     page_size: int = 1000) -> Path:
    """Extract whole months; return snapshot directory only when all reconcile.

    Existing complete partitions are verified and reused. An interrupted month
    has no committed payload and is re-extracted as a unit.
    """
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", snapshot_id):
        raise ValueError("invalid snapshot_id")
    ranges = list(months(start, end))
    client = client or SocrataClient(version=version, page_size=page_size)
    root = Path(output_dir) / snapshot_id
    schema_path = root / "source_schema.json"
    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    else:
        metadata = client.metadata()
        schema = {"dataset_id": DATASET, "columns": [{"field_name": c.get("fieldName"),
                  "data_type": c.get("dataTypeName")} for c in metadata["columns"]],
                  "rows_updated_at": metadata.get("rowsUpdatedAt"),
                  "view_last_modified": metadata.get("viewLastModified")}
        write_once(schema_path, schema)
    source_path = root / "data_source_manifest.json"
    if source_path.exists():
        source_manifest = json.loads(source_path.read_text(encoding="utf-8"))
    else:
        source_manifest = {"snapshot_id": snapshot_id, "source": f"{HOST}/resource/{DATASET}.json",
                           "api_version": client.version, "schema_hash": digest(schema),
                           "retrieval_started_at": datetime.now(UTC).isoformat(),
                           "created_date_interpretation": "source calendar_date; preserve civil date without UTC shift",
                           "range_start": start.isoformat(), "range_end": end.isoformat()}
        write_once(source_path, source_manifest)
    if (source_manifest.get("range_start") != start.isoformat() or
            source_manifest.get("range_end") != end.isoformat() or
            source_manifest.get("schema_hash") != digest(schema) or
            source_manifest.get("api_version") != client.version):
        raise SourceError("snapshot configuration conflicts with existing manifest")
    partitions = []
    for month_start, month_end in ranges:
        base = root / "partitions" / month_start.strftime("%Y-%m")
        manifest_path = base / "manifest.json"
        payload_path = base / "aggregates.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("status") != "complete" or not payload_path.exists():
                raise SourceError(f"incomplete committed partition {month_start:%Y-%m}")
            rows = json.loads(payload_path.read_text(encoding="utf-8"))
            if digest(rows) != manifest.get("payload_hash") or validate_rows(rows, month_start, month_end) != manifest.get("grouped_count"):
                raise SourceError(f"partition integrity failure {month_start:%Y-%m}")
        else:
            if payload_path.exists():
                # An interrupted write has no committed manifest. Discard the
                # one orphan file and re-extract the entire calendar month.
                payload_path.unlink()
            rows, manifest = extract_partition(client, month_start, month_end)
            manifest.update({"snapshot_id": snapshot_id, "endpoint": source_manifest["source"],
                             "schema_hash": digest(schema),
                             "source_metadata_version": schema["rows_updated_at"],
                             "extracted_at": datetime.now(UTC).isoformat()})
            write_once(payload_path, rows)
            write_once(manifest_path, manifest)
        partitions.append(manifest)
    summary = {"snapshot_id": snapshot_id, "status": "complete", "partition_ids": [p["partition_id"] for p in partitions],
               "aggregate_rows": sum(p["aggregate_rows"] for p in partitions),
               "source_count": sum(p["source_count"] for p in partitions),
               "partition_manifest_hashes": {p["partition_id"]: digest(p) for p in partitions}}
    write_once(root / "snapshot_manifest.json", summary)
    return root
