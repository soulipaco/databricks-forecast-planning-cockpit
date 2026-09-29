"""Three-series real-data integration smoke; never a benchmark result."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

from nyc311_forecast.evaluation.metrics import score
from nyc311_forecast.evaluation.splits import bounded_history, future_dates
from nyc311_forecast.models import prophet_adapter, snaive
from nyc311_forecast.models.prophet_adapter import ProphetParameters

ROOT = Path(__file__).resolve().parents[1]
SILVER = ROOT / "data/silver/development-silver-20260929/daily_requests.jsonl"
SELECTION = ROOT / "data/series_manifest/selection-v1.json"
OUTPUT = ROOT / "evidence/development_smoke.json"
ORIGIN = date(2024, 10, 31)
PARAMETERS = ProphetParameters(0.05, 1.0, "additive")


def main() -> None:
    git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        raise RuntimeError("Commit code and data before the smoke run")
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    chosen = [row["series_id"] for row in selection["candidates"] if row["selected"]][:3]
    if len(chosen) != 3:
        raise ValueError("Expected three selected series")
    by_series: dict[str, list[dict]] = {name: [] for name in chosen}
    for line in SILVER.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["series_id"] in by_series:
            by_series[row["series_id"]].append({"ds": date.fromisoformat(row["ds"]), "y": row["y"]})
    output = {
        "status": "smoke_only_not_benchmark",
        "run_id": f"development-smoke-{git_sha[:12]}",
        "code_sha": git_sha,
        "silver_snapshot_id": "development-silver-20260929",
        "selection_manifest": str(SELECTION.relative_to(ROOT)),
        "origin": ORIGIN.isoformat(),
        "horizon_days": 28,
        "prophet_parameter_source": "fixed_smoke_values_not_tuned",
        "prophet_parameters": asdict(PARAMETERS),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "results": [],
    }
    dates = future_dates(ORIGIN)
    for series_id in chosen:
        rows = by_series[series_id]
        history = bounded_history(rows, ORIGIN)
        actual_by_date = {row["ds"]: row["y"] for row in rows}
        actual = [actual_by_date[day] for day in dates]
        for label, adapter, config in (
            ("snaive7_smoke", snaive, None),
            ("prophet_fixed_smoke", prophet_adapter, PARAMETERS),
        ):
            forecast = adapter.forecast(
                history, dates, series_id=series_id, origin=ORIGIN,
                model_config=config, execution_context=None,
            )
            prediction = [value.prediction for value in forecast.predictions]
            lower = [value.lower for value in forecast.predictions]
            upper = [value.upper for value in forecast.predictions]
            metrics = score(
                actual, prediction, [row["y"] for row in history],
                None if all(value is None for value in lower) else lower,
                None if all(value is None for value in upper) else upper,
            )
            output["results"].append({
                "series_id": series_id,
                "smoke_label": label,
                "wall_seconds": forecast.wall_seconds,
                "metrics": asdict(metrics),
                "forecast": [
                    {"ds": value.ds.isoformat(), "lead_day": value.lead_day,
                     "prediction": value.prediction, "lower": value.lower,
                     "upper": value.upper, "actual": actual_by_date[value.ds]}
                    for value in forecast.predictions
                ],
            })
    content = json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if OUTPUT.exists() and OUTPUT.read_text(encoding="utf-8") != content:
        raise ValueError("Smoke artifact exists; use a new run ID and path")
    OUTPUT.write_text(content, encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
