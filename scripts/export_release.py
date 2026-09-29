"""Export the minimum release evidence tables from the stored final benchmark artifacts.

Every number is derived from `final_three_model_*.json` and its summary; nothing is typed in.
Featured-series selection follows 08_EVIDENCE_RELEASE.md deterministically.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import median

MODELS = ("snaive7", "prophet_tuned", "ai_forecast_v2")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def featured_series(summary: dict) -> dict[str, str]:
    """Median native-vs-Prophet difference, worst native difference, a baseline winner."""
    rows = sorted(
        (r for r in summary["per_series"]
         if r["ai_forecast_v2_wape"] is not None and r["prophet_tuned_wape"] is not None),
        key=lambda r: (r["ai_forecast_v2_wape"] - r["prophet_tuned_wape"], r["series_id"]),
    )
    chosen = {
        "median_native_minus_prophet": rows[(len(rows) - 1) // 2]["series_id"],
        "worst_native_minus_prophet": rows[-1]["series_id"],
    }
    baseline = [r for r in summary["per_series"]
                if r["snaive7_wape"] is not None
                and r["snaive7_wape"] <= min(r["prophet_tuned_wape"], r["ai_forecast_v2_wape"])]
    if baseline:
        chosen["baseline_wins"] = min(baseline, key=lambda r: r["series_id"])["series_id"]
    return chosen


def export(combined_path: Path, summary_path: Path, out: Path, release_id: str) -> dict:
    combined = json.loads(combined_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if combined.get("status") != "final_three_model_benchmark":
        raise ValueError("Expected the final three-model benchmark artifact")
    if summary.get("run_id") != combined["run_id"]:
        raise ValueError("Summary belongs to a different run")
    out.mkdir(parents=True, exist_ok=True)

    leaderboard = []
    for model in MODELS:
        m = summary["models"][model]
        leaderboard.append({
            "model_id": model,
            "primary_median_series_wape": m["primary_median_series_wape"],
            "paired_pooled_wape": m["paired_pooled_wape"],
            "paired_abs_error_sum": m["paired_abs_error_sum"],
            "paired_actual_sum": m["paired_actual_sum"],
            "paired_signed_bias": m["paired_signed_bias"],
            "median_cell_mase": m["median_cell_mase"],
            "wape_lead_1_7": m["pooled_wape_by_lead_window"]["1-7"],
            "wape_lead_8_14": m["pooled_wape_by_lead_window"]["8-14"],
            "wape_lead_15_28": m["pooled_wape_by_lead_window"]["15-28"],
            "interval_coverage_80": m["interval_coverage"],
            "interval_hits": m["interval_hits"],
            "interval_n": m["interval_n"],
            "expected_cells": m["expected_cells"],
            "complete_cells": m["complete_cells"],
            "paired_series_origin_pairs": summary["paired_series_origin_pairs"],
            "run_id": combined["run_id"],
        })
    _write_csv(out / "leaderboard.csv", leaderboard)

    series_scores = [
        {"series_id": c["series_id"], "origin": c["origin"], "model_id": c["model_id"],
         "status": c["status"], "n_predictions": c["n_predictions"],
         **{k: c.get("metrics", {}).get(k) for k in (
             "abs_error_sum", "actual_sum", "signed_error_sum", "wape", "signed_bias", "mase",
             "interval_n", "interval_hits", "interval_width_sum", "interval_score_sum")},
         "query_id": c.get("query_id")}
        for c in sorted(combined["evaluation_cells"],
                        key=lambda c: (c["series_id"], c["origin"], c["model_id"]))
    ]
    _write_csv(out / "series_scores.csv", series_scores)

    failures = [
        {"series_id": a["series_id"], "origin": a["origin"], "model_id": a["model_id"],
         "attempt_no": a["attempt_no"], "error_class": a.get("error_class"),
         "safe_error_message": a.get("safe_error_message"),
         "cell_final_status": next(c["status"] for c in combined["evaluation_cells"]
                                   if (c["series_id"], c["origin"], c["model_id"])
                                   == (a["series_id"], a["origin"], a["model_id"]))}
        for a in combined["attempts"] if a["status"] != "success"
    ]
    fields = ["series_id", "origin", "model_id", "attempt_no", "error_class",
              "safe_error_message", "cell_final_status"]
    with (out / "failures.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(failures)

    runtime = []
    for model in MODELS:
        attempts = [a for a in combined["attempts"]
                    if a["model_id"] == model and a["status"] == "success"]
        walls = [a["wall_seconds"] for a in attempts if a.get("wall_seconds") is not None]
        metrics = [a.get("query_metrics") or {} for a in attempts]
        exec_ms = [q["execution_time_ms"] for q in metrics if q.get("execution_time_ms")]
        runtime.append({
            "phase": "final_fit_and_predict", "model_id": model,
            "execution_surface": "Databricks serverless SQL warehouse (trial)"
            if model == "ai_forecast_v2" else "local Python process",
            "successful_cells": len(attempts),
            "median_wall_seconds_per_cell": median(walls) if walls else None,
            "total_wall_seconds": sum(walls) if walls else None,
            "median_warehouse_execution_ms": median(exec_ms) if exec_ms else None,
            "cached_results": sum(1 for q in metrics if q.get("result_from_cache")),
            "note": "Wall time includes queue/network for SQL; excludes Prophet tuning cost"
            if model != "snaive7" else "No fitting",
        })
    _write_csv(out / "runtime.csv", runtime)

    featured = featured_series(summary)
    sample = [
        {"featured_as": role, **{k: v[k] for k in (
            "series_id", "origin", "model_id", "ds", "lead_day", "actual", "prediction",
            "lower", "upper")}}
        for role, series in featured.items()
        for v in combined["forecast_values"]
        if v["series_id"] == series and v["origin"] == combined["origins"][-1]
    ]
    _write_csv(out / "prediction_sample.csv", sample)

    manifest = {
        "release_id": release_id,
        "status": "release_candidate_unpublished",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "final_run_id": combined["run_id"],
        "source_runs": combined["source_runs"],
        "code_sha_by_source": combined["code_sha_by_source"],
        "source_run_sha256": combined["source_sha256"],
        "combined_sha256": _sha(combined_path),
        "summary_sha256": _sha(summary_path),
        "silver_snapshot_id": combined["silver_snapshot_id"],
        "silver_sha256": combined["silver_sha256"],
        "featured_series": featured,
        "tables": {name: _sha(out / name) for name in (
            "leaderboard.csv", "series_scores.csv", "failures.csv", "runtime.csv",
            "prediction_sample.csv")},
    }
    (out / "release_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combined", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("evidence"))
    parser.add_argument("--release-id", required=True)
    args = parser.parse_args()
    if (args.out / "release_manifest.json").exists():
        raise ValueError("Release manifest exists; use a new release directory")
    print(json.dumps(export(args.combined, args.summary, args.out, args.release_id), indent=2))


if __name__ == "__main__":
    main()
