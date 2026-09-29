"""Model adapters and their shared, Spark-free forecast contract."""

from .contracts import ForecastResult, Prediction, validate_inputs

__all__ = ["ForecastResult", "Prediction", "validate_inputs"]
