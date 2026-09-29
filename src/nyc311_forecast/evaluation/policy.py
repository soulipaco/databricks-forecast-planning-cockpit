"""Paired-population headline and development-only champion rules."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from statistics import median

from nyc311_forecast.evaluation.metrics import Score, pooled_wape
from nyc311_forecast.evaluation.splits import DEVELOPMENT_ORIGINS

SIMPLICITY_ORDER = ("snaive7", "ai_forecast_v2", "prophet_tuned")


@dataclass(frozen=True)
class ChampionChoice:
    series_id: str
    model_id: str | None
    development_wape: float | None
    qualifying_models: tuple[str, ...]
    reason: str


def choose_development_champion(
    series_id: str,
    cells: Mapping[tuple[str, date], Score],
    *,
    tolerance: float = 0.05,
) -> ChampionChoice:
    """Require both development origins; no 2025 dates may enter selection."""
    if not 0 <= tolerance <= 1:
        raise ValueError("Invalid tolerance")
    if any(origin not in DEVELOPMENT_ORIGINS for _, origin in cells):
        raise ValueError("Champion selection may use only development origins")
    qualified: dict[str, float] = {}
    for model in SIMPLICITY_ORDER:
        scores = [cells.get((model, origin)) for origin in DEVELOPMENT_ORIGINS]
        if any(item is None or item.n != 28 for item in scores):
            continue
        value = pooled_wape(scores)
        if value is not None:
            qualified[model] = value
    if not qualified:
        return ChampionChoice(series_id, None, None, (), "no_model_completed_both_development_origins")
    best = min(qualified.values())
    retained = tuple(
        model for model in SIMPLICITY_ORDER
        if model in qualified and (qualified[model] == 0 if best == 0 else qualified[model] <= best * (1 + tolerance))
    )
    chosen = retained[0]
    return ChampionChoice(series_id, chosen, qualified[chosen], tuple(qualified), "within_tolerance_then_simplicity")


def paired_macro_wape(
    cells: Mapping[tuple[str, str, date], Score],
    *,
    models: Sequence[str],
    series_ids: Sequence[str],
    origins: Sequence[date],
) -> dict:
    """Score only cells with a complete 28-day result for every candidate."""
    if not models or not series_ids or not origins:
        raise ValueError("Expected evaluation grid is empty")
    expected = len(series_ids) * len(origins)
    complete_by_model = {
        model: sum(
            (cell := cells.get((model, series, origin))) is not None and cell.n == 28
            for series in series_ids for origin in origins
        )
        for model in models
    }
    paired = [
        (series, origin) for series in series_ids for origin in origins
        if all((cell := cells.get((model, series, origin))) is not None and cell.n == 28 for model in models)
    ]
    by_model_series: dict[tuple[str, str], list[Score]] = defaultdict(list)
    for series, origin in paired:
        for model in models:
            by_model_series[(model, series)].append(cells[(model, series, origin)])
    result = {}
    for model in models:
        per_series = {
            series: pooled_wape(by_model_series[(model, series)])
            for series in series_ids if by_model_series[(model, series)]
        }
        valid = [value for value in per_series.values() if value is not None]
        result[model] = {
            "macro_median_wape": median(valid) if valid else None,
            "valid_series": len(valid),
            "complete_cells": complete_by_model[model],
            "expected_cells": expected,
            "paired_cells": len(paired),
        }
    return {
        "models": result,
        "paired_cells": len(paired),
        "expected_cells": expected,
        "unrestricted_comparison": all(count / expected >= 0.95 for count in complete_by_model.values()),
    }
