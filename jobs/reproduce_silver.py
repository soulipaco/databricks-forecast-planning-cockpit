"""Job entry: rebuild development Silver from committed snapshots and compare hashes."""

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from nyc311_forecast.data.materialize import materialize_development

SILVER_ID = "development-silver-20260929"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    root = parser.parse_args().root
    committed = json.loads(
        (root / "data/silver" / SILVER_ID / "manifest.json").read_text(encoding="utf-8")
    )
    with tempfile.TemporaryDirectory() as tmp:
        output = materialize_development(
            root / "data/snapshots/selection-2021-2023-20260929",
            root / "data/snapshots/development-2024-20260929",
            root / "data/series_manifest/selection-v1.json",
            Path(tmp),
            snapshot_id=SILVER_ID,
        )
        payload = (output / "daily_requests.jsonl").read_bytes()
    report = {
        "snapshot_id": SILVER_ID,
        "row_count": payload.count(b"\n"),
        "daily_payload_hash": hashlib.sha256(payload).hexdigest(),
        "expected_row_count": committed["row_count"],
        "expected_payload_hash": committed["daily_payload_hash"],
    }
    report["reproduced"] = (
        report["row_count"] == report["expected_row_count"]
        and report["daily_payload_hash"] == report["expected_payload_hash"]
    )
    print(json.dumps(report, indent=2))
    return 0 if report["reproduced"] else 1


if __name__ == "__main__":
    code = main()
    if code:
        raise SystemExit(code)
