"""Typed, validated configuration without credentials in files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MODELS = ("snaive7", "prophet_tuned", "ai_forecast_v2")


@dataclass(frozen=True)
class Config:
    experiment_id: str
    snapshot_id: str
    protocol_version: str = "1.0"
    horizon_days: int = 28
    max_concurrency: int = 2
    max_retries: int = 2
    task_timeout_seconds: int = 1800
    workspace_host: str | None = None
    warehouse_id: str | None = None
    catalog: str | None = None
    schema: str | None = None
    volume: str | None = None

    def __post_init__(self) -> None:
        if not self.experiment_id or not self.snapshot_id:
            raise ValueError("experiment_id and snapshot_id are required")
        if self.horizon_days != 28:
            raise ValueError("Protocol v1 requires a 28-day horizon")
        if not 1 <= self.max_concurrency <= 2:
            raise ValueError("max_concurrency must be 1 or 2")
        if not 0 <= self.max_retries <= 2:
            raise ValueError("max_retries must be 0 through 2")
        if not 60 <= self.task_timeout_seconds <= 7200:
            raise ValueError("task_timeout_seconds must be 60 through 7200")
        for name in ("catalog", "schema", "volume"):
            value = getattr(self, name)
            if value is not None and not IDENTIFIER.fullmatch(value):
                raise ValueError(f"Invalid SQL identifier for {name}")
        if self.workspace_host and not self.workspace_host.startswith("https://"):
            raise ValueError("workspace_host must use HTTPS")


def load_config(path: str | Path) -> Config:
    with Path(path).open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise TypeError("Configuration must be a mapping")
    allowed = set(Config.__dataclass_fields__)
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"Unknown configuration keys: {', '.join(sorted(unknown))}")
    return Config(**raw)
