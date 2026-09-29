"""Render a source-backed 2024 two-model development diagnostic figure."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def series_wape(source: dict) -> list[dict]:
    if source.get("status") != "partial_two_model_development_not_benchmark":
        raise ValueError("Expected labeled development results")
    if source.get("expected_cells") != 84 or source.get("complete_cells") != 84:
        raise ValueError("This chart requires the complete two-model development grid")
    grouped = defaultdict(list)
    for cell in source["evaluation_cells"]:
        if cell["status"] != "complete" or cell["n_actual"] != 28 or cell["n_predictions"] != 28:
            raise ValueError("Incomplete chart source cell")
        grouped[(cell["series_id"], cell["model_id"])].append(cell["metrics"])
    if len(grouped) != 42 or any(len(rows) != 2 for rows in grouped.values()):
        raise ValueError("Expected two origins for each series and model")
    rows = []
    for series_id in source["series_ids"]:
        values = {}
        for model_id in ("snaive7", "prophet_tuned"):
            cells = grouped[(series_id, model_id)]
            denominator = sum(item["actual_sum"] for item in cells)
            if denominator <= 0:
                raise ValueError(f"Undefined WAPE for {series_id}")
            values[model_id] = sum(item["abs_error_sum"] for item in cells) / denominator
        rows.append({"series_id": series_id, **values})
    return sorted(rows, key=lambda row: row["snaive7"] - row["prophet_tuned"])


def render(rows: list[dict], output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    blue, gold, charcoal, grid = "#2463A6", "#C88B19", "#263442", "#DFE4E9"
    fig, ax = plt.subplots(figsize=(12, 12.5), dpi=180)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    for index, row in enumerate(rows):
        ax.plot(
            [row["snaive7"], row["prophet_tuned"]],
            [index, index],
            color="#AEB8C2",
            linewidth=1.15,
            zorder=1,
        )
    ax.scatter(
        [row["snaive7"] for row in rows],
        range(len(rows)),
        s=37,
        marker="s",
        color=gold,
        label="Weekly naïve",
        zorder=3,
    )
    ax.scatter(
        [row["prophet_tuned"] for row in rows],
        range(len(rows)),
        s=42,
        marker="o",
        color=blue,
        label="Tuned Prophet",
        zorder=3,
    )
    ax.set_yticks(range(len(rows)), [row["series_id"] for row in rows])
    ax.invert_yaxis()
    ax.set_xlim(left=0)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("WAPE across two 28-day development forecasts", color=charcoal, labelpad=10)
    ax.grid(axis="x", color=grid, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#AEB8C2")
    ax.tick_params(axis="y", length=0, labelsize=9, colors=charcoal, pad=7)
    ax.tick_params(axis="x", colors=charcoal)
    ax.legend(loc="upper right", frameon=False, ncol=2, fontsize=10)
    fig.suptitle(
        "2024 development: series-level forecast error",
        x=0.38,
        y=0.985,
        fontsize=17,
        fontweight="bold",
        color=charcoal,
    )
    fig.text(
        0.38,
        0.956,
        "21 borough × problem-family series · same two origins for both models",
        fontsize=10.5,
        color="#536575",
    )
    fig.text(
        0.38,
        0.018,
        "Partial two-model diagnostic only · no ai_forecast v2 result or 2025 evaluation",
        fontsize=9,
        color="#536575",
    )
    fig.subplots_adjust(left=0.38, right=0.97, top=0.925, bottom=0.07)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, facecolor="white")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    render(series_wape(source), args.output)
    print(str(args.output))


if __name__ == "__main__":
    main()
