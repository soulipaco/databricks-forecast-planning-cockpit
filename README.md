# NYC 311 forecast planning cockpit

**Question:** Can one Databricks SQL forecasting function be competitive with a tuned Prophet pipeline while requiring less model-specific engineering?

This repository is an **in-progress portfolio implementation** of a planned benchmark and planning dashboard. It has no verified benchmark result, deployed dashboard, or public release evidence yet. The question above is a test, not a conclusion.

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
| Real source snapshot and selected series | Pending | `evidence/data_card.md` and release manifest |
| Three-model forecast and score tables | Pending | `evidence/leaderboard.csv`, `series_scores.csv`, `failures.csv` |
| Workspace dashboard inspection | Pending | Release validation report and screenshots |
| Public result and reproducible release | Pending | Release manifest, claims ledger, chart data and code |

The [evidence directory](evidence/README.md) currently contains templates, not benchmark outputs. Synthetic fixtures used for local tests must stay visibly labelled and excluded from result claims.

## Repository guide

- [Start here](00_START_HERE.md): handoff and reading map.
- [Data specification](02_DATA_SPEC.md): source, aggregation, selection and quality rules.
- [Benchmark protocol](03_BENCHMARK_PROTOCOL.md): cutoffs, adapters, metrics and pairing rules.
- [Architecture contracts](04_ARCHITECTURE_CONTRACTS.md): intended interfaces and data grains.
- [Workspace operations](07_WORKSPACE_OPERATIONS.md): intended access, deployment and recovery flow.
- [Evidence and release gates](08_EVIDENCE_RELEASE.md): required artifacts and review criteria.
- [Communication drafts](portfolio/README.md): carousel wireframe and later measurement log.

The companion [Prophet forecasting MLOps repository](https://github.com/soulipaco/prophet-forecasting-mlops) is the intended source of reusable model engineering. Its code and license must be audited and a commit pinned before claiming integration or parity.

## Reproduction status

The current CLI implements local `doctor` configuration validation, `ingest` aggregate extraction, `select-series` for an exactly complete 2021–2023 snapshot, `materialize-development` for the verified 2021–2024 daily spine, and a `smoke` command for the pinned Databricks v2 capability check. `doctor` reports whether workspace inputs are present; it **does not verify workspace access**. The `smoke` command has only been tested with a fake API response; no Databricks workspace check has completed for this repository. The other commands in [the backlog](05_BACKLOG_PARALLEL_WORK.md)—including `tune`, `freeze`, `benchmark`, `evaluate`, `export-evidence` and `validate-release`—are proposed and not implemented. Do not treat those examples as runnable instructions.

The locally reconciled selection data cover 2021–2023 and select 21 series; the 2024 development extract and daily spine are also present. See the [data card](evidence/data_card.md) for counts, hashes, exclusions and exact commands. No 2025 data or model comparison results are present.

Once implemented and verified, this section should give an exact environment, configuration example, commands, snapshot/run identifiers, expected outputs and workspace prerequisites. A release will link every headline claim through a calculation and prediction rows to its source snapshot. The native model's training-corpus overlap with public historical data may be unknown even after the project pipeline's leakage checks.
