"""Render the 2025 final benchmark series-level WAPE dot plot from the stored summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

MODELS = (  # fixed categorical order; shape is a second, colour-independent encoding
    ("snaive7", "Weekly seasonal naïve", "#eb6834", "s"),
    ("prophet_tuned", "Tuned Prophet (20 trials/series)", "#1baf7a", "D"),
    ("ai_forecast_v2", "Databricks ai_forecast v2", "#2a78d6", "o"),
)


def rows_from(summary: dict) -> list[dict]:
    if summary.get("status") != "final_three_model_benchmark_summary":
        raise ValueError("Expected the final benchmark summary")
    rows = [r for r in summary["per_series"]
            if all(r[f"{m}_wape"] is not None for m, *_ in MODELS)]
    if len(rows) != len(summary["per_series"]):
        raise ValueError("Every series needs a defined WAPE for all models")
    return sorted(rows, key=lambda r: r["ai_forecast_v2_wape"] - r["prophet_tuned_wape"],
                  reverse=True)


def render(summary: dict, output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    rows = rows_from(summary)
    ink, muted, grid = "#1f2328", "#5b6470", "#e3e6ea"
    fig, ax = plt.subplots(figsize=(12, 12.5), dpi=180)
    for i, row in enumerate(rows):
        values = [row[f"{m}_wape"] for m, *_ in MODELS]
        ax.plot([min(values), max(values)], [i, i], color="#c3c8cf", linewidth=1.2, zorder=1)
    for model, label, color, marker in MODELS:
        ax.scatter([r[f"{model}_wape"] for r in rows], range(len(rows)), s=46, marker=marker,
                   color=color, edgecolor="white", linewidth=1.2, zorder=3, label=label)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r["series_id"].replace("|", " · ") for r in rows], color=ink, fontsize=10)
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlim(0, None)
    ax.grid(axis="x", color=grid, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(grid)
    ax.tick_params(colors=muted, length=0)
    ax.set_xlabel("WAPE over 12 monthly origins × 28-day horizon (lower is better)",
                  color=muted, fontsize=10)
    m = summary["models"]
    fig.suptitle("NYC 311 daily requests, 2025 backtest: error by series and model",
                 x=0.03, ha="left", fontsize=16, color=ink, weight="bold")
    ax.set_title(
        "Median series WAPE: v2 {:.1%} · Prophet {:.1%} · naïve {:.1%}. "
        "Sorted by v2 minus Prophet (v2 relatively best at the bottom).".format(
            m["ai_forecast_v2"]["primary_median_series_wape"],
            m["prophet_tuned"]["primary_median_series_wape"],
            m["snaive7"]["primary_median_series_wape"]),
        loc="left", fontsize=10.5, color=muted, pad=34)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, frameon=False,
              fontsize=10, labelcolor=ink, handletextpad=0.3, columnspacing=1.6)
    fig.text(0.03, 0.012,
             f"Source: NYC Open Data 311 (erm2-nwe9); run {summary['run_id']}. "
             f"{summary['paired_series_origin_pairs']}/{summary['expected_series_origin_pairs']}"
             " paired series-origins. Retrospective backtest; v2 pretraining corpus unknown.",
             fontsize=8.5, color=muted)
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    fig.savefig(output, facecolor="white")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(json.loads(args.summary.read_text(encoding="utf-8")), args.output)
    print(args.output)


if __name__ == "__main__":
    main()
