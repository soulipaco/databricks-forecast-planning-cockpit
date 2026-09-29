"""Export auditable partial 2024 two-model diagnostic totals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nyc311_forecast.evaluation.development_report import summarize


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output exists; preserve prior evidence")
    data = json.loads(args.input.read_text(encoding="utf-8"))
    report = summarize(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
