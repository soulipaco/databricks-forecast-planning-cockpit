from pathlib import Path

import pytest

from nyc311_forecast.data.selection import select_from_snapshot


def test_one_month_probe_cannot_select_series(tmp_path: Path):
    probe = Path("data/snapshots/jan-2023-20260929")
    with pytest.raises(ValueError, match="2021–2023"):
        select_from_snapshot(probe, "experiment", tmp_path / "series.json")
    assert not (tmp_path / "series.json").exists()
