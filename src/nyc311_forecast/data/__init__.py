"""Deterministic source normalization and development-only series selection."""

from .series import daily_spine, normalize, select_series

__all__ = ["daily_spine", "normalize", "select_series"]
