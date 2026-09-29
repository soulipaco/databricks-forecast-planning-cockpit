"""Seven-day seasonal naïve forecast without fitting or future target reads."""

from __future__ import annotations

from collections.abc import Iterable
from time import perf_counter
from typing import Any

from .contracts import ForecastResult, publish_prediction, validate_inputs

MODEL_ID = "snaive7"


def forecast(
    history: Any,
    future_dates: Iterable[Any],
    *,
    series_id: str,
    origin: Any,
    model_config: Any = None,
    execution_context: Any = None,
) -> ForecastResult:
    started = perf_counter()
    rows, dates, cutoff = validate_inputs(history, future_dates, origin=origin)
    if not series_id:
        raise ValueError("series_id is required")
    last_week = tuple(row.y for row in rows[-7:])
    predictions = tuple(
        publish_prediction(ds, lead, last_week[(lead - 1) % 7]) for lead, ds in enumerate(dates, 1)
    )
    return ForecastResult(
        MODEL_ID,
        series_id,
        cutoff,
        predictions,
        wall_seconds=perf_counter() - started,
        lineage={
            "method": "repeat_final_seven_observed_days",
            "training_last_date": cutoff.isoformat(),
        },
    )
