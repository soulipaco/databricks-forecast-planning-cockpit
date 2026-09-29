# Contributing

This is a portfolio benchmark with a **frozen protocol**. Issues and pull requests that improve reproducibility, fix defects or challenge the method are welcome.

## Rules that keep the result honest

- **Do not change frozen inputs.** `docs/design/03_BENCHMARK_PROTOCOL.md`, `conf/benchmark.yaml`, the series manifest, the tuning checkpoints and the development run are hash-locked in `evidence/freeze_manifest.json`. Any change to them requires a new protocol version and a new run; it must not overwrite v1 evidence.
- **Never tune on 2025 results.** New ideas, such as bias correction, need their own protocol and data.
- **Keep failures visible.** A failed cell stays in the expected grid; do not drop it to improve a score.
- **Every public number needs a calculation.** Add or update a row in `evidence/claims.csv`, citing the stored artifact.
- **No private data.** Do not commit workspace hosts, tokens, account identifiers, local paths or record-level 311 data.

## Development

```bash
uv sync --all-extras
uv run ruff check src tests scripts portfolio jobs
uv run pytest -q
```

Workspace steps need a local, untracked config such as `conf/trial.local.yaml`; see the README.
