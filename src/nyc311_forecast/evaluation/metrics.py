"""Auditable ratio-of-sums forecast scores."""

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from statistics import mean


@dataclass(frozen=True)
class Score:
    n: int
    abs_error_sum: float
    actual_sum: float
    signed_error_sum: float
    wape: float | None
    signed_bias: float | None
    mase_denominator: float | None
    mase: float | None
    interval_n: int
    interval_hits: int
    interval_width_sum: float
    interval_score_sum: float


def score(actual: Sequence[float], prediction: Sequence[float], train: Sequence[float], lower: Sequence[float] | None = None, upper: Sequence[float] | None = None) -> Score:
    if not actual or len(actual) != len(prediction):
        raise ValueError("Actual and prediction grids must be nonempty and equal")
    if len(train) != 1095:
        raise ValueError("MASE requires the 1,095-day training window")
    if any(not isfinite(float(v)) for values in (actual, prediction, train) for v in values):
        raise ValueError("Non-finite metric input")
    if any(v < 0 for v in actual):
        raise ValueError("Negative request count")
    if (lower is None) != (upper is None):
        raise ValueError("Interval bounds must be paired")
    if lower is not None and (len(lower) != len(actual) or len(upper) != len(actual)):
        raise ValueError("Interval grid length mismatch")
    if lower is not None and any(not isfinite(float(v)) for values in (lower, upper) for v in values):
        raise ValueError("Non-finite interval bound")
    errors = [float(p) - float(a) for a, p in zip(actual, prediction)]
    abs_sum = sum(abs(e) for e in errors)
    volume = sum(abs(float(a)) for a in actual)
    signed = sum(errors)
    seasonal = mean(abs(float(train[i]) - float(train[i - 7])) for i in range(7, len(train)))
    hits = 0
    width = 0.0
    interval_score = 0.0
    if lower is not None:
        for y, lo, hi in zip(actual, lower, upper):
            if lo > hi:
                raise ValueError("Invalid interval order")
            hits += lo <= y <= hi
            width += hi - lo
            interval_score += hi - lo + (10 * (lo - y) if y < lo else 10 * (y - hi) if y > hi else 0)
    return Score(len(actual), abs_sum, volume, signed, abs_sum / volume if volume else None, signed / volume if volume else None, seasonal, (abs_sum / len(actual)) / seasonal if seasonal else None, len(actual) if lower is not None else 0, hits, width, interval_score)


def pooled_wape(cells: Sequence[Score]) -> float | None:
    denominator = sum(c.actual_sum for c in cells)
    return sum(c.abs_error_sum for c in cells) / denominator if denominator else None
