from collections import Counter
from datetime import date

import pytest

from nyc311_forecast.data.series import BOROUGHS, daily_spine, normalize, select_series


def test_unknown_borough_is_quarantined_and_alias_is_explicit():
    counts, excluded = normalize([
        {"request_date": "2023-01-01", "borough": "BRONX", "complaint_type": "Old", "request_count": "2"},
        {"request_date": "2023-01-01", "borough": "Unspecified", "complaint_type": "Old", "request_count": "7"},
    ], {"Old": "New"})
    assert counts[("BRONX", "New", date(2023, 1, 1))] == 2
    assert excluded["UNSPECIFIED"] == 7


def test_missing_borough_and_complaint_are_quarantined():
    counts, excluded = normalize([
        {"request_date": "2021-01-01", "complaint_type": "Dirty Conditions", "request_count": "2"},
        {"request_date": "2021-01-01", "borough": "BRONX", "request_count": "3"},
    ])
    assert not counts
    assert excluded["<MISSING_BOROUGH>"] == 2
    assert excluded["<MISSING_COMPLAINT_TYPE>"] == 3


def test_incomplete_partition_stays_null():
    selected = [{"selected": True, "series_id": "BRONX|A", "borough": "BRONX", "problem_family": "A"}]
    rows = daily_spine(Counter(), selected, date(2023, 1, 31), date(2023, 2, 2), {"2023-01"})
    assert [(r["y"], r["is_zero_filled"], r["quality_status"]) for r in rows] == [
        (0, True, "complete"), (None, False, "source_partition_incomplete")]


def test_selection_requires_development_window_and_four_boroughs():
    # Sparse keys represent a stable daily count when present, with one
    # intentionally ineligible borough per family.
    start, end = date(2021, 1, 1), date(2024, 1, 1)
    from datetime import timedelta
    counts = Counter()
    for i in range((end - start).days):
        day = start + timedelta(days=i)
        for family in ("A", "B", "C"):
            for borough in BOROUGHS[:4]:
                counts[(borough, family, day)] = 25
    manifest = select_series(counts, start, end)
    assert sum(row["selected"] for row in manifest) == 12
    assert all(row["reason"] == "series_threshold" for row in manifest if row["borough"] == "STATEN ISLAND")
    with pytest.raises(ValueError, match="2021-2023"):
        select_series(counts, start, date(2025, 1, 1))
