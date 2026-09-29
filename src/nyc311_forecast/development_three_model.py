"""Combine the two-model and native v2 2024 runs into one three-model development grid.

Both inputs must share series, origins and the hashed Silver/selection snapshot. The output
feeds the freeze gate and development champion policy; it is not a 2025 benchmark result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from nyc311_forecast.config import MODELS
from nyc311_forecast.evaluation.metrics import Score, pooled_wape
from nyc311_forecast.evaluation.policy import choose_development_champion, paired_macro_wape

STATUS = "three_model_development_not_benchmark"
SHARED_KEYS = ("series_ids", "origins", "silver_sha256", "silver_snapshot_id", "selection_sha256")


def combine(
    two_model: dict,
    native: dict,
    *,
    source_hashes: dict[str, str],
    input_statuses: tuple[str, str] = (
        "partial_two_model_development_not_benchmark",
        "native_v2_development_not_benchmark",
    ),
    status: str = STATUS,
    run_prefix: str = "development-three-model",
) -> dict:
    if two_model.get("status") != input_statuses[0]:
        raise ValueError("Expected the labeled two-model run")
    if native.get("status") != input_statuses[1]:
        raise ValueError("Expected the labeled native v2 run")
    if native.get("series_limit"):
        raise ValueError("A series-limited pilot cannot enter the development grid")
    for key in SHARED_KEYS:
        if two_model.get(key) != native.get(key):
            raise ValueError(f"Runs disagree on {key}")
    cells = two_model["evaluation_cells"] + native["evaluation_cells"]
    keys = [(c["origin"], c["series_id"], c["model_id"]) for c in cells]
    expected = {
        (o, s, m) for o in two_model["origins"] for s in two_model["series_ids"] for m in MODELS
    }
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError("Combined cells differ from the three-model grid")
    complete = {k for k, c in zip(keys, cells) if c["status"] == "complete"}
    paired = sum(
        all((o, s, m) in complete for m in MODELS)
        for o in two_model["origins"] for s in two_model["series_ids"]
    )
    return {
        "status": status,
        "run_id": f"{run_prefix}-{source_hashes['two_model'][:6]}"
                  f"{source_hashes['native'][:6]}",
        "source_runs": {"two_model": two_model["run_id"], "native": native["run_id"]},
        "source_sha256": source_hashes,
        "code_sha_by_source": {"two_model": two_model["code_sha"], "native": native["code_sha"]},
        "model_ids": list(MODELS),
        **{key: two_model[key] for key in SHARED_KEYS},
        "prophet_parameters_by_series": two_model["prophet_parameters_by_series"],
        "expected_cells": len(expected),
        "complete_cells": len(complete),
        "failed_cells": len(expected) - len(complete),
        "paired_three_model_cells": paired,
        "attempts": two_model["attempts"] + native["attempts"],
        "evaluation_cells": cells,
        "forecast_values": two_model["forecast_values"] + native["forecast_values"],
    }


def _scores(combined: dict) -> dict[tuple[str, str, date], Score]:
    return {
        (c["model_id"], c["series_id"], date.fromisoformat(c["origin"])): Score(**c["metrics"])
        for c in combined["evaluation_cells"]
        if c["status"] == "complete"
    }


def summarize(combined: dict) -> dict:
    """Paired development statistics with numerators, plus the frozen champion rule."""
    scores = _scores(combined)
    series_ids = combined["series_ids"]
    origins = [date.fromisoformat(o) for o in combined["origins"]]
    macro = paired_macro_wape(scores, models=MODELS, series_ids=series_ids, origins=origins)
    paired = [
        (s, o) for s in series_ids for o in origins
        if all((m, s, o) in scores for m in MODELS)
    ]
    models = {}
    for model in MODELS:
        selected = [scores[(model, s, o)] for s, o in paired]
        actual = sum(x.actual_sum for x in selected)
        interval_n = sum(x.interval_n for x in selected)
        models[model] = {
            "paired_abs_error_sum": sum(x.abs_error_sum for x in selected),
            "paired_signed_error_sum": sum(x.signed_error_sum for x in selected),
            "paired_actual_sum": actual,
            "paired_pooled_wape": pooled_wape(selected),
            "paired_signed_bias": sum(x.signed_error_sum for x in selected) / actual
            if actual else None,
            "series_macro_median_wape": macro["models"][model]["macro_median_wape"],
            "interval_n": interval_n,
            "interval_hits": sum(x.interval_hits for x in selected),
            "interval_coverage": sum(x.interval_hits for x in selected) / interval_n
            if interval_n else None,
            "complete_cells": macro["models"][model]["complete_cells"],
        }
    champions = []
    for series_id in series_ids:
        choice = choose_development_champion(
            series_id,
            {(m, o): scores[(m, series_id, o)] for m in MODELS for o in origins
             if (m, series_id, o) in scores},
        )
        champions.append({"series_id": series_id, "model_id": choice.model_id,
                          "development_wape": choice.development_wape, "reason": choice.reason})
    native, prophet = models["ai_forecast_v2"], models["prophet_tuned"]
    competitive = {
        # Protocol primary score: median series-level WAPE over the paired cells.
        "primary_wape_relative_to_prophet": native["series_macro_median_wape"]
        / prophet["series_macro_median_wape"] - 1,
        "pooled_wape_relative_to_prophet": native["paired_pooled_wape"]
        / prophet["paired_pooled_wape"] - 1,
        "abs_bias_gap_pp": 100 * (abs(native["paired_signed_bias"])
                                  - abs(prophet["paired_signed_bias"])),
        "native_cell_coverage": native["complete_cells"] / macro["expected_cells"],
    }
    competitive["meets_illustrative_rule"] = (
        competitive["primary_wape_relative_to_prophet"] <= 0.05
        and competitive["abs_bias_gap_pp"] <= 2
        and competitive["native_cell_coverage"] >= 0.95
    )
    return {
        "status": "three_model_2024_development_diagnostic_only",
        "run_id": combined["run_id"],
        "expected_series_origin_pairs": macro["expected_cells"],
        "paired_series_origin_pairs": len(paired),
        "models": models,
        "practically_competitive_rule_on_development": competitive,
        "development_champions": champions,
        "champion_counts": {
            str(m).lower(): sum(c["model_id"] == m for c in champions) for m in (*MODELS, None)
        },
        "limitation": "Two 2024 development origins only; the 2025 evaluation is unopened. "
                      "Native v2 ran in a trial workspace, Prophet and naive locally.",
    }


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--two-model", required=True, type=Path)
    parser.add_argument("--native", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.output, args.summary):
        if path.exists():
            raise ValueError(f"{path} exists; preserve prior evidence")
    combined = combine(
        json.loads(args.two_model.read_text(encoding="utf-8")),
        json.loads(args.native.read_text(encoding="utf-8")),
        source_hashes={"two_model": _sha(args.two_model), "native": _sha(args.native)},
    )
    report = summarize(combined)
    for path, payload in ((args.output, combined), (args.summary, report)):
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k != "development_champions"},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
