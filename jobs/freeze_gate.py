"""Job entry: report protocol freeze blockers; exits non-zero while blocked."""

import argparse
import os
from pathlib import Path

from nyc311_forecast.cli import main

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    os.chdir(parser.parse_args().root)
    code = main(
        [
            "freeze",
            "--config", "conf/benchmark.yaml",
            "--development-run", "evidence/development_two_model_full_20260929.json",
            "--check-only",
        ]
    )
    if code:
        raise SystemExit(code)
