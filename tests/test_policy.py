from datetime import date

import pytest

from nyc311_forecast.evaluation.metrics import score
from nyc311_forecast.evaluation.policy import choose_development_champion, paired_macro_wape
from nyc311_forecast.evaluation.splits import DEVELOPMENT_ORIGINS


def _score(prediction: float):
    return score([100.0] * 28, [prediction] * 28, list(range(1095)))


def test_champion_uses_both_origins_and_simplicity_tie_break():
    cells = {
        (model, origin): _score(prediction)
        for model, prediction in (("snaive7", 103.1), ("ai_forecast_v2", 103.05), ("prophet_tuned", 103))
        for origin in DEVELOPMENT_ORIGINS
    }
    choice = choose_development_champion("s", cells)
    assert choice.model_id == "snaive7"  # 3.1% is within 5% relative of 3%
    del cells[("snaive7", DEVELOPMENT_ORIGINS[1])]
    choice = choose_development_champion("s", cells)
    assert choice.model_id == "ai_forecast_v2"
    with pytest.raises(ValueError, match="development"):
        choose_development_champion("s", {("snaive7", date(2025, 1, 31)): _score(100)})


def test_paired_macro_uses_shared_cells_and_reports_coverage():
    origins = DEVELOPMENT_ORIGINS
    cells = {
        (model, series, origin): _score(prediction)
        for model, prediction in (("snaive7", 110), ("prophet_tuned", 105))
        for series in ("a", "b") for origin in origins
    }
    del cells[("prophet_tuned", "b", origins[1])]
    report = paired_macro_wape(cells, models=("snaive7", "prophet_tuned"), series_ids=("a", "b"), origins=origins)
    assert report["paired_cells"] == 3
    assert report["models"]["prophet_tuned"]["complete_cells"] == 3
    assert report["models"]["snaive7"]["macro_median_wape"] == pytest.approx(0.1)
    assert not report["unrestricted_comparison"]
