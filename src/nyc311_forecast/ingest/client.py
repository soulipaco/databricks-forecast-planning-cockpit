"""Small SODA2/SODA3 adapter for source-side daily aggregates."""

from __future__ import annotations

import json
import os
import random
import time
from datetime import date
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HOST = "https://data.cityofnewyork.us"
DATASET = "erm2-nwe9"
TRANSIENT = {429, 500, 502, 503, 504}


class SourceError(RuntimeError):
    """A source request or response could not be trusted."""


class SocrataClient:
    def __init__(self, *, version: str = "soda2", token: str | None = None,
                 page_size: int = 1000, timeout: int = 60,
                 transport=None, sleeper=time.sleep, rng=None):
        if version not in {"soda2", "soda3"}:
            raise ValueError("version must be soda2 or soda3")
        if not 1 <= page_size <= 50000:
            raise ValueError("page_size outside 1..50000")
        self.version = version
        self.token = token if token is not None else os.environ.get("SOCRATA_APP_TOKEN")
        if version == "soda3" and not self.token:
            raise ValueError("SODA3 needs SOCRATA_APP_TOKEN")
        self.page_size = page_size
        self.timeout = timeout
        self.transport = transport or urlopen
        self.sleeper = sleeper
        self.rng = rng or random.Random()

    def _request(self, url: str, body: bytes | None = None):
        headers = {"Accept": "application/json", "User-Agent": "nyc311-forecast-benchmark/0.1"}
        if self.token:
            headers["X-App-Token"] = self.token
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=body, headers=headers, method="POST" if body is not None else "GET")
        try:
            with self.transport(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except HTTPError:
            raise
        except (URLError, TimeoutError, ValueError) as exc:
            raise SourceError(f"source request failed: {type(exc).__name__}") from exc
        return payload

    def metadata(self) -> dict:
        value = self._request(f"{HOST}/api/views/{DATASET}.json")
        if not isinstance(value, dict) or value.get("id") != DATASET:
            raise SourceError("unexpected source metadata")
        fields = {c.get("fieldName"): c.get("dataTypeName") for c in value.get("columns", [])}
        required = {"created_date", "borough", "complaint_type", "unique_key"}
        if not required <= fields.keys():
            raise SourceError("required source fields missing")
        if fields["created_date"] != "calendar_date":
            raise SourceError(f"created_date type changed: {fields['created_date']}")
        return value

    @staticmethod
    def where(start: date, end: date) -> str:
        return (f"created_date >= '{start.isoformat()}T00:00:00' "
                f"AND created_date < '{end.isoformat()}T00:00:00'")

    def query(self, select: str, where: str, *, group: str | None = None,
              order: str | None = None, offset: int = 0, page_number: int = 1) -> list[dict]:
        if self.version == "soda2":
            params = {"$select": select, "$where": where, "$limit": self.page_size,
                      "$offset": offset}
            if group:
                params["$group"] = group
            if order:
                params["$order"] = order
            url = f"{HOST}/resource/{DATASET}.json?{urlencode(params)}"
            value = self._request(url)
        else:
            sql = f"SELECT {select} WHERE {where}"
            if group:
                sql += f" GROUP BY {group}"
            if order:
                sql += f" ORDER BY {order}"
            body = json.dumps({"query": sql, "page": {"pageNumber": page_number,
                               "pageSize": self.page_size}, "includeSynthetic": False}).encode()
            value = self._request(f"{HOST}/api/v3/views/{DATASET}/query.json", body)
        if not isinstance(value, list):
            raise SourceError("query did not return a JSON array")
        return value

    def grouped_page(self, start: date, end: date, *, offset=0, page_number=1):
        return self.query("date_trunc_ymd(created_date) AS request_date, borough, "
                          "complaint_type, count(*) AS request_count", self.where(start, end),
                          group="request_date, borough, complaint_type",
                          order="request_date, borough, complaint_type",
                          offset=offset, page_number=page_number)

    def source_count(self, start: date, end: date) -> int:
        rows = self.query("count(*) AS source_count", self.where(start, end))
        if len(rows) != 1:
            raise SourceError("source count query returned unexpected row count")
        return parse_count(rows[0].get("source_count"))


def parse_count(value) -> int:
    if isinstance(value, bool) or value is None:
        raise SourceError("invalid count")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SourceError("invalid count") from exc
    if str(value) != str(parsed) or parsed < 0:
        raise SourceError("count must be a non-negative integer")
    return parsed


def retry_delay(error: HTTPError, attempt: int, rng) -> float:
    value = error.headers.get("Retry-After") if error.headers else None
    if value:
        try:
            return min(60.0, max(0.0, float(value)))
        except ValueError:
            try:
                return min(60.0, max(0.0, (parsedate_to_datetime(value).timestamp() - time.time())))
            except (ValueError, TypeError):
                pass
    return min(30.0, 2 ** (attempt - 1) + rng.uniform(0, 1))
