"""Render the README figures from stored final-benchmark artifacts only.

- hero_forecasts.png: actuals vs all three 28-day forecasts for the featured series that
  release_manifest.json selected by the protocol rule, at the final origin.
- scoreboard.png: primary WAPE and signed bias as two separate panels (no dual axis).
- bias_by_origin.png: pooled signed bias by forecast origin for each model.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

MODELS = (  # fixed categorical order and a colour-independent marker per model
    ("snaive7", "Weekly seasonal naïve", "#eb6834", "s"),
    ("prophet_tuned", "Tuned Prophet", "#1baf7a", "D"),
    ("ai_forecast_v2", "Databricks ai_forecast v2", "#2a78d6", "o"),
)
INK, MUTED, GRID, ACTUAL = "#1f2328", "#5b6470", "#e3e6ea", "#1f2328"
HISTORY_DAYS = 42


def _style(plt) -> None:
    plt.rcParams.update({
        "font.size": 11, "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
        "xtick.color": MUTED, "ytick.color": MUTED, "axes.titlecolor": INK,
        "axes.spines.top": False, "axes.spines.right": False,
    })


def _footer(fig, text: str) -> None:
    fig.text(0.012, 0.012, text, fontsize=8.5, color=MUTED, ha="left")


def hero(combined: dict, silver: dict, featured: dict, out: Path, plt) -> None:
    origin = combined["origins"][-1]
    o = date.fromisoformat(origin)
    roles = [("median_native_minus_prophet", "Typical case (median v2 − Prophet gap)"),
             ("worst_native_minus_prophet", "Hardest case for v2 (largest gap)")]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6), dpi=170, sharey=False)
    for ax, (role, subtitle) in zip(axes, roles):
        series = featured[role]
        hist = [(o - timedelta(days=i), silver[(series, (o - timedelta(days=i)).isoformat())])
                for i in range(HISTORY_DAYS - 1, -1, -1)]
        rows = [v for v in combined["forecast_values"]
                if v["series_id"] == series and v["origin"] == origin]
        by_model = defaultdict(list)
        for v in sorted(rows, key=lambda r: r["ds"]):
            by_model[v["model_id"]].append(v)
        actual = [(date.fromisoformat(v["ds"]), v["actual"]) for v in by_model["snaive7"]]
        v2 = by_model["ai_forecast_v2"]
        ax.fill_between([date.fromisoformat(v["ds"]) for v in v2], [v["lower"] for v in v2],
                        [v["upper"] for v in v2], color="#2a78d6", alpha=0.13, linewidth=0,
                        label="v2 80% interval")
        ax.plot([d for d, _ in hist] + [d for d, _ in actual],
                [y for _, y in hist] + [y for _, y in actual],
                color=ACTUAL, linewidth=1.6, label="Actual requests", zorder=4)
        ax.axvspan(o, date.fromisoformat(v2[-1]["ds"]), color="#f3f5f7", zorder=0)
        for model, label, color, _marker in MODELS:
            pts = by_model[model]
            baseline = model == "snaive7"
            ax.plot([date.fromisoformat(v["ds"]) for v in pts], [v["prediction"] for v in pts],
                    color=color, linewidth=1.3 if baseline else 2.4,
                    alpha=0.75 if baseline else 1.0, label=label, zorder=3)
        ax.axvline(o, color=MUTED, linewidth=1, linestyle=(0, (3, 3)))
        ax.text(o, ax.get_ylim()[1], "  forecast origin", color=MUTED, fontsize=9, va="top")
        ax.set_title(f"{series.replace('|', ' · ')}\n{subtitle}", loc="left", fontsize=12)
        ax.set_ylim(bottom=0)
        ax.set_ylabel("Daily service requests")
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.tick_params(axis="x", labelrotation=0)
        import matplotlib.dates as mdates
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0, interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(0.008, 0.94), ncol=5,
               frameon=False, fontsize=10)
    fig.suptitle(f"28-day forecasts from {o:%d %b %Y}, as each model saw the history",
                 x=0.012, ha="left", fontsize=15, color=INK, weight="bold")
    _footer(fig, "Series chosen by the protocol's featured-series rule (release_manifest.json); "
                 "final origin. NYC Open Data 311, run " + combined["run_id"] + ".")
    fig.tight_layout(rect=(0, 0.035, 1, 0.925))
    fig.savefig(out, facecolor="white")
    plt.close(fig)


def scoreboard(summary: dict, out: Path, plt) -> None:
    from matplotlib.ticker import PercentFormatter

    m = summary["models"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2), dpi=170)
    labels = [label for _, label, _, _ in MODELS]
    colors = [color for _, _, color, _ in MODELS]
    wape = [m[k]["primary_median_series_wape"] for k, *_ in MODELS]
    bias = [m[k]["paired_signed_bias"] for k, *_ in MODELS]
    for ax, values, title in ((a1, wape, "Error: median series WAPE (lower is better)"),
                              (a2, bias, "Bias: forecast minus actual volume (0 is best)")):
        bars = ax.barh(labels, values, color=colors, height=0.56)
        ax.invert_yaxis()
        ax.axvline(0, color=MUTED, linewidth=0.9)
        ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_title(title, loc="left", fontsize=12)
        for bar, value in zip(bars, values):
            x = bar.get_width()
            ax.text(x + (0.006 if x >= 0 else -0.006), bar.get_y() + bar.get_height() / 2,
                    f"{value:+.1%}" if ax is a2 else f"{value:.1%}", va="center",
                    ha="left" if x >= 0 else "right", color=INK, fontsize=11)
    a1.set_xlim(0, max(wape) * 1.25)
    a2.set_xlim(min(bias) * 1.45, max(0.04, max(bias) * 3))
    a2.set_yticklabels([])
    a2.tick_params(axis="y", length=0)
    a1.tick_params(axis="y", length=0)
    fig.suptitle("Most accurate, but consistently short", x=0.012, ha="left", fontsize=15,
                 color=INK, weight="bold")
    _footer(fig, f"{summary['paired_series_origin_pairs']}/{summary['expected_series_origin_pairs']} "
                 "paired series-origins, 12 monthly 2025 origins × 28 days. Run "
                 + summary["run_id"] + ".")
    fig.tight_layout(rect=(0, 0.05, 1, 0.97))
    fig.savefig(out, facecolor="white")
    plt.close(fig)


def bias_by_origin(combined: dict, out: Path, plt) -> None:
    from matplotlib.ticker import PercentFormatter

    sums = defaultdict(lambda: [0.0, 0.0])
    for cell in combined["evaluation_cells"]:
        s = sums[(cell["model_id"], cell["origin"])]
        s[0] += cell["metrics"]["signed_error_sum"]
        s[1] += cell["metrics"]["actual_sum"]
    origins = combined["origins"]
    xs = [date.fromisoformat(o) for o in origins]
    fig, ax = plt.subplots(figsize=(12, 4.4), dpi=170)
    ax.axhline(0, color=MUTED, linewidth=1)
    for model, label, color, marker in MODELS:
        ys = [sums[(model, o)][0] / sums[(model, o)][1] for o in origins]
        ax.plot(xs, ys, color=color, linewidth=2, marker=marker, markersize=6, label=label)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{d:%d %b %Y}" if i in (0, 1) else f"{d:%d %b}"
                        for i, d in enumerate(xs)], fontsize=9.5)
    ax.set_xlabel("Forecast origin (each point scores the following 28 days)")
    ax.set_ylabel("Signed bias / actual volume")
    ax.legend(frameon=False, ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0))
    fig.suptitle("v2 forecast below actual demand at all 12 origins", x=0.012, ha="left",
                 fontsize=15, color=INK, weight="bold")
    _footer(fig, "Pooled over 21 series per origin. Run "
                 + combined["run_id"] + ".")
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    fig.savefig(out, facecolor="white")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combined", type=Path, default=Path("evidence/final_three_model_20260929.json"))
    parser.add_argument("--summary", type=Path, default=Path("evidence/final_three_model_summary_20260929.json"))
    parser.add_argument("--manifest", type=Path, default=Path("evidence/release_manifest.json"))
    parser.add_argument("--silver", type=Path, default=Path("data/silver/evaluation-silver-20260929/daily_requests.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("portfolio"))
    args = parser.parse_args()
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _style(plt)
    combined = json.loads(args.combined.read_text(encoding="utf-8"))
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    featured = json.loads(args.manifest.read_text(encoding="utf-8"))["featured_series"]
    silver = {}
    with args.silver.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            silver[(row["series_id"], row["ds"])] = row["y"]
    hero(combined, silver, featured, args.out / "hero_forecasts.png", plt)
    scoreboard(summary, args.out / "scoreboard.png", plt)
    bias_by_origin(combined, args.out / "bias_by_origin.png", plt)
    print("wrote hero_forecasts.png, scoreboard.png, bias_by_origin.png")


if __name__ == "__main__":
    main()
