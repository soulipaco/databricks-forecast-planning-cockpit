# NYC 311 forecast planning cockpit

**Question:** Can one Databricks SQL forecasting function be competitive with a tuned Prophet pipeline while requiring less model-specific engineering?

This repository is a **reproducible portfolio benchmark** (release candidate `nyc311-benchmark-v1.0-rc1`, not yet published). The protocol was frozen and hash-locked before any 2025 data was retrieved; all three models were then evaluated on twelve 2025 month-end origins.

## Result

On 21 NYC 311 series × 12 origins × 28 days (252/252 paired series-origins, 21,168 predictions per the [arithmetic check](evidence/final_prediction_arithmetic_20260929.json)):

| Model | Median series WAPE (primary) | Pooled WAPE | Signed bias | 80% interval coverage |
|---|---|---|---|---|
| Weekly seasonal naïve | 25.0% | 32.4% | -4.8% | n/a |
| Tuned Prophet (20 trials/series) | 19.5% | 34.2% | 0.5% | 77.7% |
| Databricks `ai_forecast` v2 | **17.1%** | **25.3%** | -14.3% | 77.9% |

- `ai_forecast` v2 had the lowest error: 12.4% lower median series WAPE than tuned Prophet, and the lowest WAPE on 17 of 21 series.
- It **systematically under-forecast**: pooled bias -14.3% versus Prophet's 0.5%, concentrated in heating and residential-noise series. Under the pre-registered rule (error no more than 5% worse **and** absolute bias no more than 2 points worse) it is therefore **not** "practically competitive" despite the accuracy lead.
- Tuned Prophet beat naïve on the median series but not on pooled volume-weighted WAPE, driven by large errors on high-volume residential-noise series.
- Runtime is not a like-for-like comparison: v2 took a median 5.3 s per series-origin through a serverless SQL warehouse; Prophet refits took 0.26 s locally, excluding its separate tuning. No monetary cost was measured.

![Series-level 2025 WAPE by model](portfolio/final_benchmark_2025.png)

Limitations: a retrospective backtest on a current snapshot of one public dataset; the v2 foundation model's pretraining corpus is unknown and may include public NYC data; v2 ran in a Databricks trial workspace because Free Edition cannot enable the network access its runtime needs ([decision record](docs/adr/native_v2_runtime_blocker.md)). All figures trace to [`evidence/leaderboard.csv`](evidence/leaderboard.csv), [`series_scores.csv`](evidence/series_scores.csv) and the [release manifest](evidence/release_manifest.json).

**For:** BI and analytics engineers deciding how much custom forecasting code a daily planning workload needs. **Start with:** the [benchmark protocol](03_BENCHMARK_PROTOCOL.md), then inspect the [evidence guide](evidence/README.md) as outputs become available.

## The planned comparison

The workload is daily **NYC 311 service-request counts** by borough and problem family. These are service requests, not total call volume, and this independent project has no NYC affiliation. The plan compares a weekly seasonal naïve baseline, a pinned Prophet adapter, and Databricks `ai_forecast` v2 on the same selected series, history and 28-day forecast dates. Model-specific fitting or invocation is only one part of the work; ingestion, evaluation, governance and reporting are shared responsibilities.

The [protocol](03_BENCHMARK_PROTOCOL.md) specifies selection from 2021–2023, Prophet tuning and development checks in 2024, and twelve month-end 2025 evaluation origins. The first seven days are a slice of each 28-day forecast. Primary reporting uses median series-level 28-day WAPE on complete paired cells, with coverage, bias, intervals, failures and runtime shown separately. The 2025 evaluation must not guide tuning or series selection.

The intended product is a code-managed Databricks AI/BI dashboard that reads stored forecasts and scores. Its capacity scenarios will be explicitly illustrative; NYC 311 data alone cannot establish staffing needs or savings. See the [product brief](06_DASHBOARD_PRODUCT.md).

## Current status and evidence

See [PROJECT_STATE.md](PROJECT_STATE.md) for the implementation ledger and [the validation report](evidence/validation_report.md) for each release gate.

| Item | Status | Evidence |
|---|---|---|
| Data 2021–2025 | 60/60 monthly partitions reconciled; 2025 retrieved only after freeze | [Data card](evidence/data_card.md), `data/silver/evaluation-silver-20260929/manifest.json` |
| Protocol freeze | Frozen and hash-locked at `c5fdacc`, tag `protocol-v1.0-frozen`; deviations D1–D3 registered before freeze | [Freeze manifest](evidence/freeze_manifest.json), [protocol](03_BENCHMARK_PROTOCOL.md) |
| Three-model final benchmark | 756/756 cells, 0 failures, 0 cached SQL results; arithmetic independently recomputed | [Leaderboard](evidence/leaderboard.csv), [series scores](evidence/series_scores.csv), [failures](evidence/failures.csv), [runtime](evidence/runtime.csv) |
| Claims | Five claims verified three ways (Python, SQL on Delta, plain CSV); self-review, no independent human reviewer | [Claims ledger](evidence/claims.csv) |
| Final run in Delta | 1 run, 756 attempts, 21,168 forecasts, 756 score cells; exact readback | [Persistence evidence](evidence/trial/workspace_final_persist_20260929.json) |
| Dashboard | Code-managed AI/BI results dashboard ([definition](dashboards/final_benchmark.lvdash.json)) deployed as an unpublished draft in the trial workspace; datasets API-verified; owner opened it | [Dashboard evidence](evidence/trial/workspace_final_dashboard_v2_20260929.json) |
| Public release | Not published; Git history rewritten to remove a private workspace host ([SHA map](docs/history_rewrite.md)) | — |

## Reproduce the final benchmark

From a clean checkout at the release commit (`uv sync --all-extras`), with a Databricks workspace where `ai_forecast` v2 works and a local config such as `conf/trial.local.yaml` (gitignored):

```bash
uv run python -m nyc311_forecast.final_benchmark verify-freeze
uv run --extra prophet python -m nyc311_forecast.final_benchmark local --output <new-local.json>
uv run --extra platform --extra prophet python -m nyc311_forecast.final_benchmark native --config conf/trial.local.yaml --output <new-native.json>
uv run python -m nyc311_forecast.final_benchmark combine --local <new-local.json> --native <new-native.json> --output <combined.json> --summary <summary.json>
uv run python scripts/verify_development_predictions.py --input <combined.json> --silver data/silver/evaluation-silver-20260929/daily_requests.jsonl --output <check.json>
```

Each stage refuses to run if any frozen input changed. Native v2 results can differ slightly between executions; the protocol's repeatability check has not yet been run.

## Repository guide

- [Start here](00_START_HERE.md): handoff and reading map.
- [Data specification](02_DATA_SPEC.md): source, aggregation, selection and quality rules.
- [Benchmark protocol](03_BENCHMARK_PROTOCOL.md): cutoffs, adapters, metrics and pairing rules.
- [Architecture contracts](04_ARCHITECTURE_CONTRACTS.md): intended interfaces and data grains.
- [Workspace operations](07_WORKSPACE_OPERATIONS.md): intended access, deployment and recovery flow.
- [Evidence and release gates](08_EVIDENCE_RELEASE.md): required artifacts and review criteria.
- [Communication drafts](portfolio/README.md): carousel wireframe and later measurement log.

The companion [Prophet forecasting MLOps repository](https://github.com/soulipaco/prophet-forecasting-mlops) was audited at commit `b2538be9d19abb191a2c8cf3306709e0cf7a2a0f`; the minimal attributed adaptation is described in [the adapter decision](docs/adr/prophet_adapter.md).

## Development history

The current CLI implements local `doctor` configuration validation, `ingest` aggregate extraction, `select-series` for an exactly complete 2021–2023 snapshot, `materialize-development` for the verified 2021–2024 daily spine, `deploy-tables` for the ten Delta contracts, `deploy-views` for five read-only serving views, and `smoke` for the pinned Databricks v2 capability check. `doctor` reports whether workspace inputs are present; it **does not verify workspace access**. The authenticated `smoke` query failed during the managed runtime's dependency installation; no native forecast result exists. `freeze` checks every protocol-freeze prerequisite and writes a hash manifest only when none is missing; against the current two-model run it refuses, listing the absent `ai_forecast_v2` candidate and 84/126 three-model cells ([readiness evidence](evidence/freeze_readiness_20260929.json)). The other CLI commands in [the backlog](05_BACKLOG_PARALLEL_WORK.md)—including `tune`, `benchmark`, `evaluate`, `export-evidence` and `validate-release`—are proposed and not implemented. Do not treat those examples as runnable instructions. A separate `scripts/tune_development.py` entry point is implemented for checkpointed, development-only Prophet tuning.

A [Databricks Asset Bundle](databricks.yml) defines two unscheduled, single-run serverless jobs. `prepare_data` rebuilds the development Silver rows from the committed monthly snapshots and fails unless the row count and payload hash match; its workspace run reproduced all 30,681 rows with the committed SHA-256. `development_gate` runs the freeze check and currently fails with the same two blockers. The `benchmark` and `publish_results` stages are deliberately absent until the protocol is frozen ([job evidence](evidence/workspace_bundle_jobs_20260929.json)). With Databricks CLI v0.280.0 the default Terraform engine failed on an expired signing key, so deployment used the direct engine:

```bash
DATABRICKS_BUNDLE_ENGINE=direct databricks bundle deploy -t dev
```

The locally reconciled selection data cover 2021–2023 and select 21 series; the 2024 development extract and daily spine are also present. The Silver JSONL was uploaded to a managed volume and merged into `mlops_dev.nyc311_forecast.daily_requests`. The first and repeated loads match all 30,681 source rows, with no missing, extra or changed records. See the [data card](evidence/data_card.md), [capability report](capability_report.md) and `evidence/workspace_silver_load_20260929.json` for counts, hashes, query IDs and blockers. No 2025 data or model comparison results are present.

A bounded local integration run covers three series and both 2024 development origins with seasonal naïve and fixed, untuned Prophet settings. It produced 12 complete cells and 336 forecast rows in `evidence/development_slice_20260929.json`, then persisted 1/12/336/12 run/attempt/value/score records to Delta with exact first and repeat readback ([workspace evidence](evidence/workspace_development_smoke_persist_20260929.json)). Run `uv run --extra prophet python -m nyc311_forecast.development_slice --series-limit 3 --output <new-evidence-path>` from a clean committed checkout to repeat it. This artifact is **smoke-only**, excludes native v2, and is not a benchmark result.

A separate five-trial Prophet tuning smoke completed on three selected development series using the registered inner origins and seed 42. Its [manifest and per-series trials](evidence/development_tuning_smoke_20260929/manifest.json) are traceable to commit `31ee879fa73d0f4e7e81c88fa35ad481d8f96afb`. It verifies the tuning execution path; those settings are excluded from benchmark and champion claims.

The registered **20-trial search completed for all 21 selected series** using three 2024 inner origins, with 420 completed trial records in [the tuning manifest and checkpoints](evidence/development_tuning_full_20260929/manifest.json). The resulting [full two-model 2024 development run](evidence/development_two_model_full_20260929.json) has 84/84 complete cells and 2,352 forecasts. Its [paired diagnostic calculation](evidence/development_two_model_diagnostic_20260929.json) uses the same 42 series-origin cells for each model and retains error sums and actual sums. The [Delta readback](evidence/workspace_development_two_model_persist_20260929.json) and repeat load each matched all 1 run, 84 attempts, 2,352 values and 84 evaluation cells. These are **development-only** results; they do not answer the three-model or 2025 test question. Databricks' managed v2 runtime still fails while installing `onnxruntime`, as recorded in [the blocker decision](docs/adr/native_v2_runtime_blocker.md).

The [series-level development figure](portfolio/development_two_model_2024.png) is regenerated from those same score cells by [the chart script](portfolio/build_development_chart.py). It shows where the two available models differ by series without presenting a final winner.

Once implemented and verified, this section should give an exact environment, configuration example, commands, snapshot/run identifiers, expected outputs and workspace prerequisites. A release will link every headline claim through a calculation and prediction rows to its source snapshot. The native model's training-corpus overlap with public historical data may be unknown even after the project pipeline's leakage checks.
