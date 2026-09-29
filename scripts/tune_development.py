"""Run checkpointed Prophet development tuning; never reads holdout data."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from nyc311_forecast.development_tuning import run_tuning

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--trials", type=int, choices=(5, 20), default=20)
    parser.add_argument("--series-limit", type=int)
    args = parser.parse_args()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        raise RuntimeError("Commit code and data before a traceable tuning run")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    result = run_tuning(
        ROOT / "data/series_manifest/selection-v1.json",
        ROOT / "data/silver/development-silver-20260929/daily_requests.jsonl",
        args.output_dir,
        code_sha=sha,
        n_trials=args.trials,
        series_limit=args.series_limit,
    )
    print(json.dumps({"manifest": result["manifest"], "results": result["results"]}, indent=2))


if __name__ == "__main__":
    main()
