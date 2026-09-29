"""Protocol-specific Prophet fit and per-series Optuna tuning.

The owner's MIT project at b2538be9d19abb191a2c8cf3306709e0cf7a2a0f
informed the fit/tune boundary. Its model builder and objective cannot be
imported here because they impose logistic growth, regressors, holidays and
RMSE. This adapter uses Prophet's public API with the benchmark's settings.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from math import isfinite
from time import perf_counter
from typing import Any

from .contracts import ForecastResult, Observation, publish_prediction, validate_inputs

MODEL_ID = "prophet_tuned"
UPSTREAM_SHA = "b2538be9d19abb191a2c8cf3306709e0cf7a2a0f"
INNER_ORIGINS = (date(2024, 1, 31), date(2024, 5, 31), date(2024, 9, 30))


@dataclass(frozen=True)
class ProphetParameters:
    changepoint_prior_scale: float
    seasonality_prior_scale: float
    seasonality_mode: str

    def __post_init__(self) -> None:
        if not 0.001 <= self.changepoint_prior_scale <= 0.5:
            raise ValueError("changepoint_prior_scale is outside the registered search")
        if not 0.01 <= self.seasonality_prior_scale <= 10:
            raise ValueError("seasonality_prior_scale is outside the registered search")
        if self.seasonality_mode not in ("additive", "multiplicative"):
            raise ValueError("Unsupported seasonality_mode")


@dataclass(frozen=True)
class TuningResult:
    series_id: str
    parameters: ProphetParameters
    pooled_wape: float
    trials: tuple[Mapping[str, Any], ...]
    wall_seconds: float
    seed: int = 42


def _prophet_class() -> Any:
    try:
        from prophet import Prophet
    except ImportError as exc:
        raise RuntimeError("Prophet extra is required for prophet_tuned") from exc
    return Prophet


def _frame(rows: tuple[Observation, ...]) -> Any:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("pandas is required for prophet_tuned") from exc
    return pd.DataFrame({"ds": [row.ds for row in rows], "y": [row.y for row in rows]})


def _fit_predict(
    rows: tuple[Observation, ...], dates: tuple[date, ...], parameters: ProphetParameters
) -> tuple[tuple[float, float, float], ...]:
    model = _prophet_class()(
        growth="linear",
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        holidays=None,
        interval_width=0.8,
        changepoint_prior_scale=parameters.changepoint_prior_scale,
        seasonality_prior_scale=parameters.seasonality_prior_scale,
        seasonality_mode=parameters.seasonality_mode,
    )
    model.fit(_frame(rows))
    import pandas as pd

    predicted = model.predict(pd.DataFrame({"ds": dates}))
    if len(predicted) != len(dates):
        raise ValueError("Prophet returned an incomplete forecast")
    returned_dates = tuple(pd.Timestamp(v).date() for v in predicted["ds"])
    if returned_dates != dates:
        raise ValueError("Prophet returned the wrong future dates")
    return tuple(
        (float(y), float(lo), float(hi))
        for y, lo, hi in zip(predicted["yhat"], predicted["yhat_lower"], predicted["yhat_upper"])
    )


def _parameters(model_config: Any) -> ProphetParameters:
    if isinstance(model_config, TuningResult):
        return model_config.parameters
    if isinstance(model_config, ProphetParameters):
        return model_config
    if isinstance(model_config, Mapping):
        return ProphetParameters(
            **{
                key: model_config[key]
                for key in (
                    "changepoint_prior_scale",
                    "seasonality_prior_scale",
                    "seasonality_mode",
                )
            }
        )
    raise TypeError("model_config must contain frozen Prophet parameters")


def forecast(
    history: Any,
    future_dates: Iterable[Any],
    *,
    series_id: str,
    origin: Any,
    model_config: Any,
    execution_context: Any = None,
) -> ForecastResult:
    started = perf_counter()
    rows, dates, cutoff = validate_inputs(history, future_dates, origin=origin)
    if not series_id:
        raise ValueError("series_id is required")
    parameters = _parameters(model_config)
    raw = _fit_predict(rows, dates, parameters)
    if len(raw) != 28:
        raise ValueError("Prophet returned an incomplete forecast")
    predictions = tuple(
        publish_prediction(ds, lead, y, raw_lower=lo, raw_upper=hi, interval_level=0.8)
        for lead, (ds, (y, lo, hi)) in enumerate(zip(dates, raw), 1)
    )
    return ForecastResult(
        MODEL_ID,
        series_id,
        cutoff,
        predictions,
        wall_seconds=perf_counter() - started,
        lineage={
            "upstream_sha": UPSTREAM_SHA,
            "training_last_date": cutoff.isoformat(),
            "parameters": vars(parameters).copy(),
        },
    )


def tune_series(
    history: Any,
    *,
    series_id: str,
    n_trials: int = 20,
    seed: int = 42,
    inner_origins: tuple[date, ...] = INNER_ORIGINS,
) -> TuningResult:
    """Tune only on the registered inner windows; return every trial for storage.

    ``history`` may include observations after an inner origin, but each model
    receives only the preceding 1,095 days. It must include all validation
    targets; 2025 observations should never be passed to this function.
    """
    if n_trials < 1 or not series_id:
        raise ValueError("n_trials and series_id must be positive/nonempty")
    try:
        import optuna
    except ImportError as exc:
        raise RuntimeError("Optuna extra is required for Prophet tuning") from exc
    # Validate a complete sorted daily series without requiring its last date
    # to equal a particular inner origin.
    raw = history[["ds", "y"]].to_dict("records") if hasattr(history, "columns") else list(history)
    if not raw:
        raise ValueError("Tuning history is empty")
    all_dates = [r["ds"] if isinstance(r["ds"], date) else date.fromisoformat(r["ds"]) for r in raw]
    if any(b != a + timedelta(days=1) for a, b in itertools.pairwise(all_dates)):
        raise ValueError("Tuning history must be sorted, unique and gap-free")
    if all_dates[-1] >= date(2025, 1, 1):
        raise ValueError("Tuning history must exclude the 2025 evaluation year")
    by_date = {ds: float(record["y"]) for ds, record in zip(all_dates, raw)}
    if any(not isfinite(y) or y < 0 for y in by_date.values()):
        raise ValueError("Tuning targets must be finite and non-negative")
    windows = []
    for cutoff in inner_origins:
        train_dates = tuple(cutoff - timedelta(days=i) for i in range(1094, -1, -1))
        future_dates = tuple(cutoff + timedelta(days=i) for i in range(1, 29))
        if any(ds not in by_date for ds in train_dates + future_dates):
            raise ValueError(f"Incomplete tuning window at {cutoff}")
        train = tuple(Observation(ds, by_date[ds]) for ds in train_dates)
        actual = tuple(by_date[ds] for ds in future_dates)
        windows.append((train, future_dates, actual))
    started = perf_counter()

    def objective(trial: Any) -> float:
        params = ProphetParameters(
            changepoint_prior_scale=trial.suggest_float(
                "changepoint_prior_scale", 0.001, 0.5, log=True
            ),
            seasonality_prior_scale=trial.suggest_float(
                "seasonality_prior_scale", 0.01, 10, log=True
            ),
            seasonality_mode=trial.suggest_categorical(
                "seasonality_mode", ["additive", "multiplicative"]
            ),
        )
        numerator = denominator = 0.0
        for train, future, actual in windows:
            raw_predictions = _fit_predict(train, future, params)
            if len(raw_predictions) != len(future):
                raise ValueError("Prophet returned an incomplete tuning forecast")
            for (prediction, _, _), target in zip(raw_predictions, actual):
                if not isfinite(prediction):
                    raise ValueError("Non-finite Prophet tuning prediction")
                numerator += abs(max(0.0, prediction) - target)
                denominator += abs(target)
        if denominator == 0:
            raise ValueError("Undefined pooled WAPE denominator")
        return numerator / denominator

    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=n_trials, catch=(ValueError, RuntimeError))
    trials = tuple(
        {
            "number": trial.number,
            "state": trial.state.name,
            "value": trial.value,
            "parameters": dict(trial.params),
        }
        for trial in study.trials
    )
    completed = [
        trial
        for trial in study.trials
        if trial.state.name == "COMPLETE" and trial.value is not None and isfinite(trial.value)
    ]
    if not completed:
        raise RuntimeError("All Prophet tuning trials failed")
    best = min(completed, key=lambda trial: (trial.value, trial.number))
    return TuningResult(
        series_id,
        _parameters(best.params),
        float(best.value),
        trials,
        perf_counter() - started,
        seed,
    )
