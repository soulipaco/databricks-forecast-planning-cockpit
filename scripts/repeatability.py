"""Protocol robustness check: repeat development inference three times on three series.

Uses only 2024 development data and origins. Reports the largest absolute difference in
point forecasts and interval bounds between repeats, per model; nothing is re-scored.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from nyc311_forecast.config import load_config
from nyc311_forecast.development_compare import ROOT, load_inputs, run_comparison
from nyc311_forecast.development_native import query_metrics, run_native, warehouse_executor


def _spread(runs: list[dict]) -> dict:
    """Max |difference| across repeats for each field, keyed by the same prediction cell."""
    keyed = [
        {(v["series_id"], v["origin"], v["model_id"], v["ds"]): v for v in run["forecast_values"]}
        for run in runs
    ]
    keys = set(keyed[0])
    if any(set(k) != keys for k in keyed):
        raise ValueError("Repeats produced different prediction populations")
    out: dict[str, dict] = {}
    for model in sorted({k[2] for k in keys}):
        model_keys = [k for k in keys if k[2] == model]
        fields = {}
        for field in ("prediction", "lower", "upper"):
            diffs = [
                max(r[k][field] for r in keyed) - min(r[k][field] for r in keyed)
                for k in model_keys if keyed[0][k][field] is not None
            ]
            fields[f"max_abs_diff_{field}"] = max(diffs) if diffs else None
        fields["predictions_compared"] = len(model_keys)
        out[model] = fields
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--series", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output exists; preserve prior evidence")
    code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    config = load_config(args.config)
    from databricks.sdk import WorkspaceClient

    client = WorkspaceClient(profile=config.workspace_profile)
    series_ids, by_series, parameters, provenance = load_inputs()
    series_ids = series_ids[: args.series]
    parameters = {s: parameters[s] for s in series_ids}
    local_runs, native_runs = [], []
    for repeat in range(args.repeats):
        local_runs.append(run_comparison(series_ids, by_series, parameters))
        native_runs.append(run_native(
            series_ids, by_series,
            warehouse_executor(client, config.warehouse_id,
                               timeout_seconds=config.task_timeout_seconds),
            catalog=config.catalog, schema=config.schema,
            snapshot_id=provenance["silver_snapshot_id"],
            run_tag=f"repeatability-{code_sha[:12]}-r{repeat}",
        ))
    query_ids = [a["query_id"] for r in native_runs for a in r["attempts"] if a.get("query_id")]
    metrics = query_metrics(client, query_ids)
    result = {
        "status": "development_repeatability_check",
        "code_sha": code_sha,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "series_ids": list(series_ids),
        "origins": local_runs[0]["origins"],
        "repeats": args.repeats,
        "complete_cells_per_repeat": {
            "local": [r["complete_cells"] for r in local_runs],
            "native": [r["complete_cells"] for r in native_runs],
        },
        "native_query_ids": query_ids,
        "native_queries_from_cache": sum(
            1 for q in query_ids if (metrics.get(q) or {}).get("result_from_cache")
        ),
        "spread": {**_spread(local_runs), **_spread(native_runs)},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("complete_cells_per_repeat",
                                             "native_queries_from_cache", "spread")}, indent=2))


if __name__ == "__main__":
    main()
