import json
from datetime import date
from pathlib import Path
from urllib.error import HTTPError

import pytest

from nyc311_forecast.ingest.client import SocrataClient, SourceError
from nyc311_forecast.ingest.snapshot import extract_partition, extract_snapshot, validate_rows


def test_null_group_key_kept_for_source_reconciliation():
    rows = [{"request_date": "2021-01-01T00:00:00.000", "complaint_type": "Dirty Conditions", "request_count": "2"}]
    assert validate_rows(rows, date(2021, 1, 1), date(2021, 2, 1)) == 2


class FakeClient(SocrataClient):
    def __init__(self, pages, counts):
        super().__init__(page_size=2, sleeper=lambda _: None)
        self.pages = pages
        self.counts = iter(counts)
        self.calls = []

    def source_count(self, start, end):
        return next(self.counts)

    def grouped_page(self, start, end, *, offset=0, page_number=1):
        self.calls.append((offset, page_number))
        return self.pages.get(offset, [])

    def metadata(self):
        return {"id": "erm2-nwe9", "columns": [
            {"fieldName": "created_date", "dataTypeName": "calendar_date"},
            {"fieldName": "borough", "dataTypeName": "text"},
            {"fieldName": "complaint_type", "dataTypeName": "text"},
            {"fieldName": "unique_key", "dataTypeName": "text"}],
            "rowsUpdatedAt": 1}


START, END = date(2023, 1, 1), date(2023, 2, 1)
ROWS = [
    {"request_date": "2023-01-01T00:00:00.000", "borough": "BRONX", "complaint_type": "A", "request_count": "2"},
    {"request_date": "2023-01-01T00:00:00.000", "borough": "BRONX", "complaint_type": "B", "request_count": "3"},
]


def test_full_page_requires_exhaustion_and_reconciles():
    client = FakeClient({0: ROWS, 2: []}, [5, 5])
    rows, manifest = extract_partition(client, START, END)
    assert rows == ROWS
    assert client.calls == [(0, 1), (2, 2)]
    assert manifest["page_count"] == 2
    assert manifest["source_count"] == manifest["grouped_count"] == 5


def test_count_drift_restarts_whole_partition():
    client = FakeClient({0: ROWS, 2: []}, [4, 5, 5, 5])
    _, manifest = extract_partition(client, START, END)
    assert manifest["attempts"] == 2
    assert client.calls == [(0, 1), (2, 2), (0, 1), (2, 2)]


def test_duplicate_key_rejected():
    client = FakeClient({0: [ROWS[0], ROWS[0]], 2: []}, [4] * 10)
    with pytest.raises(SourceError, match="duplicate"):
        extract_partition(client, START, END)


def test_immutable_resume_and_corruption_detection(tmp_path: Path):
    first = FakeClient({0: ROWS, 2: []}, [5, 5])
    root = extract_snapshot(START, END, tmp_path, "snap-1", client=first)
    second = FakeClient({}, [])
    assert extract_snapshot(START, END, tmp_path, "snap-1", client=second) == root
    assert second.calls == []
    payload = root / "partitions" / "2023-01" / "aggregates.json"
    payload.write_text("[]")
    with pytest.raises(SourceError, match="integrity"):
        extract_snapshot(START, END, tmp_path, "snap-1", client=second)


def test_orphan_payload_reextracts_whole_month(tmp_path: Path):
    root = tmp_path / "snap-2" / "partitions" / "2023-01"
    root.mkdir(parents=True)
    (root / "aggregates.json").write_text("broken partial download")
    client = FakeClient({0: ROWS, 2: []}, [5, 5])
    extract_snapshot(START, END, tmp_path, "snap-2", client=client)
    assert client.calls == [(0, 1), (2, 2)]
    assert json.loads((root / "aggregates.json").read_text()) == ROWS


def test_soda3_needs_token_and_uses_page_number():
    seen = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self, *_): return b"[]"

    def transport(req, timeout):
        seen.append((req.full_url, json.loads(req.data)))
        return Response()

    client = SocrataClient(version="soda3", token="fixture-token", transport=transport)
    client.grouped_page(START, END, page_number=3)
    assert seen[0][1]["page"] == {"pageNumber": 3, "pageSize": 1000}
    assert "/api/v3/views/erm2-nwe9/query.json" in seen[0][0]


def test_429_retries_partition_with_bounded_attempts():
    class Throttled(FakeClient):
        def __init__(self):
            super().__init__({0: ROWS, 2: []}, [5, 5, 5])
            self.once = True

        def grouped_page(self, *args, **kwargs):
            if self.once:
                self.once = False
                raise HTTPError("url", 429, "rate limit", {"Retry-After": "0"}, None)
            return super().grouped_page(*args, **kwargs)

    client = Throttled()
    _, manifest = extract_partition(client, START, END)
    assert manifest["attempts"] == 2
