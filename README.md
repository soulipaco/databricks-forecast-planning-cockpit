# NYC 311 forecast planning cockpit

**Question:** Can one Databricks SQL forecasting function be competitive with a tuned Prophet pipeline while requiring less model-specific engineering?

This repository is an **in-progress portfolio implementation** of a planned benchmark and planning dashboard. It has no verified benchmark result, completed planning dashboard, or public release evidence yet. A limited, unpublished development-data dashboard draft exists. The question above is a test, not a conclusion.

**For:** BI and analytics engineers deciding how much custom forecasting code a daily planning workload needs. **Start with:** the [benchmark protocol](03_BENCHMARK_PROTOCOL.md), then inspect the [evidence guide](evidence/README.md) as outputs become available.

## The planned comparison

The workload is daily **NYC 311 service-request counts** by borough and problem family. These are service requests, not total call volume, and this independent project has no NYC affiliation. The plan compares a weekly seasonal naïve baseline, a pinned Prophet adapter, and Databricks `ai_forecast` v2 on the same selected series, history and 28-day forecast dates. Model-specific fitting or invocation is only one part of the work; ingestion, evaluation, governance and reporting are shared responsibilities.

The [protocol](03_BENCHMARK_PROTOCOL.md) specifies selection from 2021–2023, Prophet tuning and development checks in 2024, and twelve month-end 2025 evaluation origins. The first seven days are a slice of each 28-day forecast. Primary reporting uses median series-level 28-day WAPE on complete paired cells, with coverage, bias, intervals, failures and runtime shown separately. The 2025 evaluation must not guide tuning or series selection.

The intended product is a code-managed Databricks AI/BI dashboard that reads stored forecasts and scores. Its capacity scenarios will be explicitly illustrative; NYC 311 data alone cannot establish staffing needs or savings. See the [product brief](06_DASHBOARD_PRODUCT.md).

## Current status and evidence

The supplied documents are a build specification. See [PROJECT_STATE.md](PROJECT_STATE.md) for the implementation ledger. Until a release has passed the [evidence gates](08_EVIDENCE_RELEASE.md), this README makes no performance, speed, cost, or deployment claim.

| Item | Current status | Where to inspect later |
|---|---|---|
| Method and intended comparison | Specified; implementation and freeze pending | [Protocol](03_BENCHMARK_PROTOCOL.md) |
| Real source snapshot and selected series | Development data verified locally and in workspace; final 2025 holdout unopened | [Data card](evidence/data_card.md) and workspace load evidence |
| Three-model forecast and score tables | Pending | `evidence/leaderboard.csv`, `series_scores.csv`, `failures.csv` |
| Workspace dashboard inspection | Unpublished development-series and data-quality draft API verified; visual check deferred and full planning product pending | [Dashboard evidence](evidence/workspace_dashboard_quality_20260929.json), release validation report and screenshots |
| Public result and reproducible release | Pending | Release manifest, claims ledger, chart data and code |

The [evidence directory](evidence/README.md) contains source and workspace validation records, development smoke results, and benchmark templates. It contains no final benchmark outputs. Synthetic fixtures used for local tests must stay visibly labelled and excluded from result claims.

## Repository guide

- [Start here](00_START_HERE.md): handoff and reading map.
- [Data specification](02_DATA_SPEC.md): source, aggregation, selection and quality rules.
- [Benchmark protocol](03_BENCHMARK_PROTOCOL.md): cutoffs, adapters, metrics and pairing rules.
- [Architecture contracts](04_ARCHITECTURE_CONTRACTS.md): intended interfaces and data grains.
- [Workspace operations](07_WORKSPACE_OPERATIONS.md): intended access, deployment and recovery flow.
- [Evidence and release gates](08_EVIDENCE_RELEASE.md): required artifacts and review criteria.
- [Communication drafts](portfolio/README.md): carousel wireframe and later measurement log.

The companion [Prophet forecasting MLOps repository](https://github.com/soulipaco/prophet-forecasting-mlops) was audited at commit `b2538be9d19abb191a2c8cf3306709e0cf7a2a0f`; the minimal attributed adaptation is described in [the adapter decision](docs/adr/prophet_adapter.md).

## Reproduction status

The current CLI implements local `doctor` configuration validation, `ingest` aggregate extraction, `select-series` for an exactly complete 2021–2023 snapshot, `materialize-development` for the verified 2021–2024 daily spine, `deploy-tables` for the ten Delta contracts, `deploy-views` for five read-only serving views, and `smoke` for the pinned Databricks v2 capability check. `doctor` reports whether workspace inputs are present; it **does not verify workspace access**. The authenticated `smoke` query failed during the managed runtime's dependency installation; no native forecast result exists. The other CLI commands in [the backlog](05_BACKLOG_PARALLEL_WORK.md)—including `tune`, `freeze`, `benchmark`, `evaluate`, `export-evidence` and `validate-release`—are proposed and not implemented. Do not treat those examples as runnable instructions. A separate `scripts/tune_development.py` entry point is implemented for checkpointed, development-only Prophet tuning.

The locally reconciled selection data cover 2021–2023 and select 21 series; the 2024 development extract and daily spine are also present. The Silver JSONL was uploaded to a managed volume and merged into `mlops_dev.nyc311_forecast.daily_requests`. The first and repeated loads match all 30,681 source rows, with no missing, extra or changed records. See the [data card](evidence/data_card.md), [capability report](capability_report.md) and `evidence/workspace_silver_load_20260929.json` for counts, hashes, query IDs and blockers. No 2025 data or model comparison results are present.

A bounded local integration run covers three series and both 2024 development origins with seasonal naïve and fixed, untuned Prophet settings. It produced 12 complete cells and 336 forecast rows in `evidence/development_slice_20260929.json`, then persisted 1/12/336/12 run/attempt/value/score records to Delta with exact first and repeat readback ([workspace evidence](evidence/workspace_development_smoke_persist_20260929.json)). Run `uv run --extra prophet python -m nyc311_forecast.development_slice --series-limit 3 --output <new-evidence-path>` from a clean committed checkout to repeat it. This artifact is **smoke-only**, excludes native v2, and is not a benchmark result.

A separate five-trial Prophet tuning smoke completed on three selected development series using the registered inner origins and seed 42. Its [manifest and per-series trials](evidence/development_tuning_smoke_20260929/manifest.json) are traceable to commit `31ee879fa73d0f4e7e81c88fa35ad481d8f96afb`. It verifies the tuning execution path; the primary protocol requires **20 trials for every selected series**, so these settings are excluded from benchmark and champion claims. The full run remains gated on a working native v2 path.

Once implemented and verified, this section should give an exact environment, configuration example, commands, snapshot/run identifiers, expected outputs and workspace prerequisites. A release will link every headline claim through a calculation and prediction rows to its source snapshot. The native model's training-corpus overlap with public historical data may be unknown even after the project pipeline's leakage checks.
