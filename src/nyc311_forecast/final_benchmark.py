"""Frozen protocol v1 final evaluation: twelve origins, three candidates, 2025 targets.

Every stage re-verifies the freeze manifest hashes and refuses to run if a frozen input
changed. Settings come only from the frozen development artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import median

from nyc311_forecast.config import MODELS, load_config
from nyc311_forecast.development_compare import ROOT, SILVER_PATH, load_inputs, run_comparison
from nyc311_forecast.development_native import (
    query_metrics,
    run_native,
    warehouse_executor,
)
from nyc311_forecast.development_three_model import combine
from nyc311_forecast.evaluation.metrics import Score, pooled_wape
from nyc311_forecast.evaluation.policy import paired_macro_wape
from nyc311_forecast.evaluation.splits import FINAL_ORIGINS

FREEZE = ROOT / "evidence/freeze_manifest.json"
FROZEN_FILES = {
    "protocol": ROOT / "docs/design/03_BENCHMARK_PROTOCOL.md",
    "config": ROOT / "conf/benchmark.yaml",
    "series_manifest": ROOT / "data/series_manifest/selection-v1.json",
    "tuning_manifest": ROOT / "evidence/development_tuning_full_20260929/manifest.json",
    "development_run": ROOT / "evidence/development_three_model_20260929.json",
}
EVAL_SILVER = ROOT / "data/silver/evaluation-silver-20260929/daily_requests.jsonl"
DEV_SUMMARY = ROOT / "evidence/development_three_model_diagnostic_20260929.json"
LOCAL_STATUS = "final_two_model_local"
NATIVE_STATUS = "final_native_v2"
FINAL_STATUS = "final_three_model_benchmark"
LEAD_WINDOWS = {"1-7": (1, 7), "8-14": (8, 14), "15-28": (15, 28), "1-28": (1, 28)}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_freeze(freeze_path: Path = FREEZE, files: dict[str, Path] = FROZEN_FILES) -> dict:
    """Refuse any final stage unless every frozen input still matches its hash."""
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze.get("status") != "frozen" or tuple(freeze.get("models", ())) != MODELS:
        raise ValueError("Protocol is not frozen for the three candidates")
    changed = [name for name, path in files.items() if _sha(path) != freeze["hashes"][name]]
    if changed:
        raise ValueError(f"Frozen inputs changed since freeze: {', '.join(changed)}")
    return freeze


def _code_sha() -> str:
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        raise RuntimeError("Commit code and inputs before a traceable final run")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False, default=str)
        stream.write("\n")


def run_local(output: Path) -> dict:
    freeze = verify_freeze()
    code_sha = _code_sha()
    series_ids, by_series, parameters, provenance = load_inputs(
        silver_path=EVAL_SILVER, last_year=2025, tuning_silver_path=SILVER_PATH
    )
    result = run_comparison(series_ids, by_series, parameters, origins=FINAL_ORIGINS,
                            status=LOCAL_STATUS)
    result.update(provenance)
    result.update({
        "run_id": f"final-local-{code_sha[:12]}", "code_sha": code_sha,
        "freeze_code_sha": freeze["code_sha"],
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "prophet_parameters_by_series": {
            s: {"changepoint_prior_scale": p.changepoint_prior_scale,
                "seasonality_prior_scale": p.seasonality_prior_scale,
                "seasonality_mode": p.seasonality_mode}
            for s, p in parameters.items()
        },
    })
    _write(output, result)
    return result


def run_final_native(config_path: Path, output: Path) -> dict:
    freeze = verify_freeze()
    code_sha = _code_sha()
    config = load_config(config_path)
    from databricks.sdk import WorkspaceClient

    client = WorkspaceClient(profile=config.workspace_profile)
    if config.workspace_host and client.config.host.rstrip("/") != config.workspace_host.rstrip("/"):
        raise ValueError("Authenticated workspace host differs from config")
    series_ids, by_series, _parameters, provenance = load_inputs(
        silver_path=EVAL_SILVER, last_year=2025, tuning_silver_path=SILVER_PATH
    )
    run_id = f"final-native-v2-{code_sha[:12]}"
    started = datetime.now(UTC)
    result = run_native(
        series_ids, by_series,
        warehouse_executor(client, config.warehouse_id,
                           timeout_seconds=config.task_timeout_seconds),
        catalog=config.catalog, schema=config.schema,
        snapshot_id=provenance["silver_snapshot_id"], run_tag=run_id,
        max_retries=config.max_retries, origins=FINAL_ORIGINS, status=NATIVE_STATUS,
    )
    query_ids = [a["query_id"] for a in result["attempts"] if a.get("query_id")]
    metadata = query_metrics(client, query_ids)
    for attempt in result["attempts"]:
        if attempt.get("query_id"):
            attempt["query_metrics"] = metadata.get(attempt["query_id"])
    result.update(provenance)
    result.update({
        "run_id": run_id, "code_sha": code_sha, "freeze_code_sha": freeze["code_sha"],
        "series_limit": None, "started_at_utc": started.isoformat(),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "workspace": "non-Free-Edition trial workspace; host kept out of public evidence",
        "delta_table": f"{config.catalog}.{config.schema}.daily_requests",
        "queries_with_metrics": sum(1 for q in query_ids if q in metadata),
        "queries_from_cache": sum(
            1 for q in query_ids if (metadata.get(q) or {}).get("result_from_cache")
        ),
    })
    _write(output, result)
    return result


def _window_totals(values: list[dict]) -> dict:
    """Pooled abs error / actual per model and lead window, from prediction rows."""
    sums: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for row in values:
        for name, (first, last) in LEAD_WINDOWS.items():
            if first <= row["lead_day"] <= last:
                total = sums[(row["model_id"], name)]
                total[0] += abs(row["prediction"] - row["actual"])
                total[1] += row["actual"]
    return {
        model: {name: sums[(model, name)][0] / sums[(model, name)][1]
                if sums[(model, name)][1] else None for name in LEAD_WINDOWS}
        for model in MODELS
    }


def summarize_final(combined: dict, dev_champions: dict[str, str]) -> dict:
    series_ids = combined["series_ids"]
    origins = [date.fromisoformat(o) for o in combined["origins"]]
    scores = {
        (c["model_id"], c["series_id"], date.fromisoformat(c["origin"])): Score(**c["metrics"])
        for c in combined["evaluation_cells"] if c["status"] == "complete"
    }
    macro = paired_macro_wape(scores, models=MODELS, series_ids=series_ids, origins=origins)
    paired = [(s, o) for s in series_ids for o in origins
              if all((m, s, o) in scores for m in MODELS)]
    paired_keys = {(s, o.isoformat()) for s, o in paired}
    paired_values = [v for v in combined["forecast_values"]
                     if (v["series_id"], v["origin"]) in paired_keys]
    windows = _window_totals(paired_values)
    models = {}
    for model in MODELS:
        selected = [scores[(model, s, o)] for s, o in paired]
        actual = sum(x.actual_sum for x in selected)
        interval_n = sum(x.interval_n for x in selected)
        mase = [x.mase for x in selected if x.mase is not None]
        models[model] = {
            "primary_median_series_wape": macro["models"][model]["macro_median_wape"],
            "paired_pooled_wape": pooled_wape(selected),
            "paired_abs_error_sum": sum(x.abs_error_sum for x in selected),
            "paired_actual_sum": actual,
            "paired_signed_error_sum": sum(x.signed_error_sum for x in selected),
            "paired_signed_bias": sum(x.signed_error_sum for x in selected) / actual
            if actual else None,
            "median_cell_mase": median(mase) if mase else None,
            "interval_n": interval_n,
            "interval_hits": sum(x.interval_hits for x in selected),
            "interval_coverage": sum(x.interval_hits for x in selected) / interval_n
            if interval_n else None,
            "mean_interval_width": sum(x.interval_width_sum for x in selected) / interval_n
            if interval_n else None,
            "pooled_wape_by_lead_window": windows[model],
            "complete_cells": macro["models"][model]["complete_cells"],
            "expected_cells": macro["expected_cells"],
        }
    native, prophet = models["ai_forecast_v2"], models["prophet_tuned"]
    rule = {
        "primary_wape_relative_to_prophet": native["primary_median_series_wape"]
        / prophet["primary_median_series_wape"] - 1,
        "abs_bias_gap_pp": 100 * (abs(native["paired_signed_bias"])
                                  - abs(prophet["paired_signed_bias"])),
        "native_cell_coverage": native["complete_cells"] / native["expected_cells"],
    }
    rule["meets_practically_competitive_rule"] = (
        rule["primary_wape_relative_to_prophet"] <= 0.05 and rule["abs_bias_gap_pp"] <= 2
        and rule["native_cell_coverage"] >= 0.95
    )
    per_series = []
    for series in series_ids:
        row = {"series_id": series, "development_champion": dev_champions.get(series)}
        for model in MODELS:
            cells = [scores[(model, series, o)] for o in origins if (model, series, o) in scores
                     and (series, o) in set(paired)]
            row[f"{model}_wape"] = pooled_wape(cells)
        per_series.append(row)
    policy_cells = [
        scores[(dev_champions[s], s, o)] for s, o in paired if dev_champions.get(s)
    ]
    series_best = {
        m: sum(1 for r in per_series if r[f"{m}_wape"] is not None and r[f"{m}_wape"] == min(
            r[f"{x}_wape"] for x in MODELS if r[f"{x}_wape"] is not None)) for m in MODELS
    }
    return {
        "status": "final_three_model_benchmark_summary",
        "run_id": combined["run_id"],
        "expected_series_origin_pairs": macro["expected_cells"],
        "paired_series_origin_pairs": len(paired),
        "unrestricted_comparison": macro["unrestricted_comparison"],
        "models": models,
        "practically_competitive_rule": rule,
        "frozen_development_champion_policy": {
            "pooled_wape": pooled_wape(policy_cells),
            "median_series_wape": median(
                pooled_wape([scores[(dev_champions[s], s, o)] for o in origins
                             if (s, o) in set(paired)]) for s in series_ids
                if dev_champions.get(s)
            ),
        },
        "series_lowest_wape_counts": series_best,
        "per_series": per_series,
        "limitations": [
            "Retrospective backtest on a current NYC Open Data snapshot, not as-published vintages.",
            "Native v2 ran in a Databricks trial workspace; naive and Prophet ran locally.",
            "The v2 foundation model's pretraining corpus is unknown; public NYC data may overlap.",
            "One dataset, 21 series, 12 origins; no universal winner or equivalence claim.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="stage", required=True)
    sub.add_parser("verify-freeze")
    local = sub.add_parser("local")
    local.add_argument("--output", type=Path, required=True)
    native = sub.add_parser("native")
    native.add_argument("--config", type=Path, required=True)
    native.add_argument("--output", type=Path, required=True)
    comb = sub.add_parser("combine")
    comb.add_argument("--local", type=Path, required=True)
    comb.add_argument("--native", type=Path, required=True)
    comb.add_argument("--output", type=Path, required=True)
    comb.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    if args.stage == "verify-freeze":
        print(json.dumps({"frozen": True, "code_sha": verify_freeze()["code_sha"]}, indent=2))
        return
    if args.output.exists():
        raise ValueError("Output exists; preserve prior evidence")
    if args.stage == "local":
        result = run_local(args.output)
    elif args.stage == "native":
        result = run_final_native(args.config, args.output)
    else:
        verify_freeze()
        if args.summary.exists():
            raise ValueError("Summary exists; preserve prior evidence")
        combined = combine(
            json.loads(args.local.read_text(encoding="utf-8")),
            json.loads(args.native.read_text(encoding="utf-8")),
            source_hashes={"two_model": _sha(args.local), "native": _sha(args.native)},
            input_statuses=(LOCAL_STATUS, NATIVE_STATUS), status=FINAL_STATUS,
            run_prefix="final-three-model",
        )
        dev = json.loads(DEV_SUMMARY.read_text(encoding="utf-8"))
        champions = {c["series_id"]: c["model_id"] for c in dev["development_champions"]}
        summary = summarize_final(combined, champions)
        _write(args.output, combined)
        _write(args.summary, summary)
        result = summary
    print(json.dumps({k: result[k] for k in result
                      if k in ("run_id", "expected_cells", "complete_cells", "failed_cells",
                               "queries_from_cache", "paired_series_origin_pairs",
                               "practically_competitive_rule")}, indent=2, default=str))


if __name__ == "__main__":
    main()
