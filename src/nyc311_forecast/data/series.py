"""Daily count preparation without holdout-driven family choices."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import median

from nyc311_forecast.ingest.client import SourceError, parse_count

BOROUGHS = ("BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "STATEN ISLAND")


def normalize(rows: list[dict], aliases: dict[str, str] | None = None):
    """Return normalized counts and quarantined unknown-borough counts."""
    aliases = aliases or {}
    counts = Counter()
    excluded = Counter()
    for row in rows:
        day = date.fromisoformat(row["request_date"][:10])
        borough = row["borough"].strip().upper()
        original = row["complaint_type"]
        family = aliases.get(original, original)
        amount = parse_count(row["request_count"])
        if borough not in BOROUGHS:
            excluded[borough] += amount
            continue
        counts[(borough, family, day)] += amount
    return counts, excluded


def select_series(counts: Counter, start: date, end: date, *, max_families=5):
    """Select by 2021-2023 data only; caller must pass its verified partitions.

    `end` is exclusive. Results carry diagnostics for every candidate.
    """
    if start != date(2021, 1, 1) or end != date(2024, 1, 1):
        raise ValueError("series selection requires exactly 2021-2023 development data")
    expected = (end - start).days
    family_total = Counter()
    by_series = defaultdict(dict)
    for (borough, family, day), value in counts.items():
        if borough not in BOROUGHS or not start <= day < end:
            raise ValueError("counts contain wrong borough or date")
        if value < 0:
            raise ValueError("negative daily count")
        family_total[family] += value
        by_series[(borough, family)][day] = value
    ranked = sorted(family_total, key=lambda family: (-family_total[family], family))
    candidates = []
    selected_families = []
    for rank, family in enumerate(ranked, 1):
        eligible = 0
        family_rows = []
        for borough in BOROUGHS:
            daily = by_series.get((borough, family), {})
            positive_days = [d for d, value in daily.items() if value > 0]
            coverage = len(positive_days) / expected
            daily_median = median([daily.get(start + timedelta(days=i), 0) for i in range(expected)])
            span = (max(positive_days) - min(positive_days)).days if positive_days else 0
            ok = coverage >= .9 and daily_median >= 20 and span >= 730
            eligible += ok
            family_rows.append({"series_id": f"{borough}|{family}", "borough": borough,
                                "problem_family": family, "family_rank": rank,
                                "positive_days": len(positive_days), "coverage": coverage,
                                "median_daily_count": daily_median, "active_span_days": span,
                                "eligible": bool(ok)})
        choose = eligible >= 4 and len(selected_families) < max_families
        if choose:
            selected_families.append(family)
        for row in family_rows:
            row["selected"] = choose and row["eligible"]
            row["reason"] = "selected" if row["selected"] else (
                "series_threshold" if not row["eligible"] else "family_not_selected")
            candidates.append(row)
    if len(selected_families) < 3:
        raise SourceError("fewer than three families qualify; protocol revision required")
    return candidates


def daily_spine(counts: Counter, selected: list[dict], start: date, end: date,
                complete_months: set[str]):
    """Zero-fill only verified complete months; mark missing days otherwise."""
    result = []
    for item in selected:
        if not item["selected"]:
            continue
        borough, family = item["borough"], item["problem_family"]
        day = start
        while day < end:
            value = counts.get((borough, family, day))
            complete = day.strftime("%Y-%m") in complete_months
            if value is None and complete:
                value = 0
            result.append({"series_id": item["series_id"], "borough": borough,
                           "problem_family": family, "ds": day, "y": value,
                           "is_zero_filled": value == 0 and (borough, family, day) not in counts and complete,
                           "quality_status": "complete" if complete else "source_partition_incomplete"})
            day += timedelta(days=1)
    return result
