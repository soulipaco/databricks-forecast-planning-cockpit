# Can one Databricks SQL function replace a forecasting pipeline?

A frozen-protocol benchmark of Databricks **`ai_forecast` v2** against a **tuned Prophet** pipeline and a **weekly seasonal naïve** baseline, on daily NYC 311 service-request counts. Data lands in Unity Catalog Delta tables, and results are served through a code-managed AI/BI dashboard.

## Result

21 series × 12 monthly origins in 2025 × 28-day horizon: 252 of 252 paired series-origins complete, 21,168 predictions per model set, no failures.

| Model | Median series WAPE (primary) | Pooled WAPE | Signed bias | 80% interval coverage |
|---|---|---|---|---|
| Weekly seasonal naïve | 25.0% | 32.4% | −4.8% | n/a |
| Tuned Prophet (20 trials/series) | 19.5% | 34.2% | +0.5% | 77.7% |
| Databricks `ai_forecast` v2 | **17.1%** | **25.3%** | −14.3% | 77.9% |

- **Lowest error:** `ai_forecast` v2 had a 12% lower median series WAPE than tuned Prophet and was the most accurate model on 17 of 21 series.
- **But it forecast too low:** its pooled bias was −14.3% of actual volume, against +0.5% for Prophet. For heating and residential-noise complaints the shortfall was about 25%.
- **Verdict under the pre-registered rule:** "practically competitive" was fixed before 2025 data was retrieved: error no more than 5% worse than Prophet **and** absolute bias no more than 2 points worse. v2 therefore does **not** qualify, despite its accuracy lead.
- **Prophet vs baseline:** Prophet beat naïve on the median series but not on volume-weighted (pooled) WAPE, because of large errors on high-volume residential-noise series.
- **Runtime is not like-for-like:** v2 took a median 5.3 s per series-origin in a serverless SQL warehouse, and Prophet refits took 0.26 s locally, excluding the separate tuning. No monetary cost was measured.

![2025 WAPE by series and model](portfolio/final_benchmark_2025.png)

Every number above is recomputed three ways: the Python summary, SQL over the persisted Delta tables, and plain arithmetic on [`evidence/series_scores.csv`](evidence/series_scores.csv). See [`evidence/`](evidence/README.md).

## How the test was kept fair

1. **Series selection (2021–2023):** 21 borough × problem-family series chosen by fixed density rules ([data spec](docs/design/02_DATA_SPEC.md)).
2. **Prophet tuning (2024):** 20 Optuna trials per series, seed 42, scored on three 2024 inner origins.
3. **Development check (2024):** all three models were run at two origins to set a per-series champion policy.
4. **Freeze:** the protocol, config, series, tuning and development results were hash-locked ([`freeze_manifest.json`](evidence/freeze_manifest.json), tag `protocol-v1.0-frozen`). Three deviations were registered beforehand ([protocol](docs/design/03_BENCHMARK_PROTOCOL.md#registered-deviations-before-freeze)).
5. **2025 evaluation:** 2025 data was downloaded only after the freeze. Every stage re-checks the freeze hashes and refuses to run if a locked input changed.

Every model received exactly the last 1,095 days before each origin. The baseline repeats the last observed week. v2 queries carried unique tags, and query history confirmed that none of the 252 queries was served from the result cache.

## Architecture

```
NYC Open Data (SODA API)
  → monthly aggregate snapshots, reconciled and hashed        src/nyc311_forecast/ingest
  → daily Silver series (21 × 1,826 days)                     src/nyc311_forecast/data
  → Unity Catalog Delta: daily_requests                       sql/tables.sql, scripts/load_workspace_silver.py
  → models
      weekly naïve, Prophet (pinned adapter)                  src/nyc311_forecast/models
      ai_forecast(..., version => '2') in a SQL warehouse     src/nyc311_forecast/platform/native_sql.py
  → scoring on a fixed grid, failures kept                    src/nyc311_forecast/evaluation
  → Delta: forecast_runs / attempts / values / evaluation_cells
  → serving views and AI/BI dashboard (reads stored rows)     sql/views.sql, dashboards/
```

Deployment is code-managed: a Databricks Asset Bundle ([`databricks.yml`](databricks.yml)) defines unscheduled, single-run serverless jobs. One of them reproduces the Silver payload byte-for-byte in the workspace.

## Running `ai_forecast` v2: what it actually needed

- **Free Edition:** the function fails while installing `onnxruntime`, because the SQL warehouse's isolated environment cannot reach PyPI, and the preview that enables that network access is not offered there ([decision record](docs/adr/native_v2_runtime_blocker.md)).
- **Trial or paid workspace:** it works once three things are in place:
  - the Predictive AI Functions preview is enabled;
  - *Enable networking for isolated workloads in Serverless SQL Warehouses* is enabled, followed by a warehouse restart;
  - a brand-new workspace has finished provisioning its system schemas (about an hour).
- **Horizon boundary:** v2 includes the `horizon` date, although the documentation calls it exclusive. The adapter requests exactly 28 days and fails on any other row count ([details](docs/adr/native_v2_horizon.md)).

## Repository layout

| Path | Contents |
|---|---|
| `src/nyc311_forecast/` | Ingestion, Silver, models, evaluation, freeze gate, final benchmark stages, Databricks adapters |
| `scripts/` | Workspace loads, Delta persistence with exact readback, dashboard deployment, release export, verification |
| `sql/` | Contract tables, serving views, headline leaderboard query |
| `dashboards/` | AI/BI dashboard definitions ([index](dashboards/README.md)) |
| `databricks.yml`, `resources/`, `jobs/` | Asset Bundle and job entry points |
| `data/` | Hashed source snapshots, series manifest, Silver payloads (aggregates only) |
| `evidence/` | Runs, scores, checks and release tables ([index](evidence/README.md)) |
| `docs/design/` | Protocol, data spec, contracts, operations and release gates |
| `docs/adr/` | Decision records |
| `tests/` | 85 tests: leakage, splits, metrics, contracts, retry policy, freeze gate, persistence |

## Reproduce

```bash
uv sync --all-extras
uv run pytest -q
uv run python -m nyc311_forecast.final_benchmark verify-freeze
```

The final run needs a Databricks workspace where v2 works, and a local, untracked config (for example `conf/trial.local.yaml`) with `workspace_host`, `workspace_profile`, `warehouse_id`, `catalog` and `schema`:

```bash
uv run --extra prophet python -m nyc311_forecast.final_benchmark local --output <local.json>
uv run --extra platform --extra prophet python -m nyc311_forecast.final_benchmark native --config conf/trial.local.yaml --output <native.json>
uv run python -m nyc311_forecast.final_benchmark combine --local <local.json> --native <native.json> --output <combined.json> --summary <summary.json>
uv run python scripts/verify_development_predictions.py --input <combined.json> --silver data/silver/evaluation-silver-20260929/daily_requests.jsonl --output <check.json>
```

In a three-repeat test, v2 produced identical outputs. Prophet's point forecasts were identical, but its interval bounds vary slightly because they are sampled.

## Limitations

- This is a retrospective backtest on a current snapshot of one public dataset, not a reconstruction of what was published at each origin.
- The v2 foundation model's training data is undisclosed and may include public NYC data.
- v2 ran in a Databricks trial workspace, while naïve and Prophet ran locally.
- The results cover 21 series and 12 origins, so they support no universal winner or equivalence claim.
- 311 service requests are not call-centre staffing; no capacity or savings claims are made.

## Credits

Data: [NYC Open Data, 311 Service Requests](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9). This is an independent project with no NYC affiliation. The Prophet adapter reuses parts of [prophet-forecasting-mlops](https://github.com/soulipaco/prophet-forecasting-mlops) at commit `b2538be` ([adapter decision](docs/adr/prophet_adapter.md)). Git history was rewritten once to remove a private workspace host; the old-to-new commit map is in [`docs/history_rewrite.md`](docs/history_rewrite.md).
