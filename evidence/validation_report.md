# Validation report — pre-release status

**Status:** Release candidate `nyc311-benchmark-v1.0-rc1`, 29 September 2026. Rows added after the final benchmark are marked (final). Not a release sign-off: independent review, dashboard inspection and public-asset review remain open.

| Gate/check | Environment | Exact command or inspection | Actual outcome | Evidence reference | Status |
|---|---|---|---|---|---|
| Data snapshot reconciliation (2021–2024) | Local + workspace | `nyc311 ingest`, `materialize-development`; Silver Delta load and repeat merge | 48/48 monthly partitions reconciled; 30,681 series-days; first and repeat loads zero missing/extra/changed | `data_card.md`, `workspace_silver_load_20260929.json`, `workspace_silver_reload_20260929.json` | passed (development scope) |
| Silver reproducibility in workspace job | Workspace (serverless job) | `databricks bundle run -t dev prepare_data` | Rebuilt 30,681 rows, payload SHA-256 equal to the committed manifest | `workspace_bundle_jobs_20260929.json` (run 674664618781380) | passed |
| Data snapshot reconciliation (2025) (final) | Local + trial workspace | `nyc311 ingest` 2025 after freeze; `materialize_evaluation`; Delta load | 12/12 months, 3,655,041 requests; 38,346 Silver rows; zero missing/extra/changed in Delta | `data_card.md`, `trial/workspace_evaluation_silver_load_20260929.json` | passed |
| Protocol and leakage checks | Local | `uv run pytest -q` (leakage, split, selection-freeze tests) | 72 passed | test suite | passed (local) |
| Protocol freeze | Local | `nyc311 freeze` on the three-model development grid | Earlier refusals retained; frozen at `c5fdacc` after 126/126 development cells; deviations D1–D3 registered first | `freeze_manifest.json`, `freeze_readiness_three_model_20260929.json` | passed |
| Forecast grid and failures (development) | Local + workspace | Two-model development run and Delta persist/readback | 84/84 cells complete, 0 failed; 1/84/2,352/84 rows read back exactly twice | `development_two_model_full_20260929.json`, `workspace_development_two_model_persist*_20260929.json` | passed (two-model development only) |
| Forecast grid and failures (final) | Local + trial workspace | `final_benchmark local/native/combine` | 756/756 cells, 0 failed attempts, 0 retries; 21,168 predictions | `final_three_model_20260929.json`, `failures.csv` | passed |
| Final metric arithmetic (final) | Local | `scripts/verify_development_predictions.py --silver …evaluation…` | All 756 cells recomputed from prediction rows; actuals equal Silver | `final_prediction_arithmetic_20260929.json` | passed |
| Cached SQL excluded (final) | Trial workspace | Query history `result_from_cache` for all 252 v2 queries | 0 cached | `final_native_v2_20260929.json`, `runtime.csv` | passed |
| Metric arithmetic and paired coverage | Local + workspace | `scripts/verify_development_predictions.py`; serving-view reconcile | All 84 score cells recomputed from 2,352 rows; 42/42 paired cells per model match in view | `development_prediction_arithmetic_20260929.json`, `workspace_development_score_reconcile_20260929.json` | passed (development only) |
| Native v2 identity | Free Edition + trial workspace | Pinned `version => '2'` smoke | Free Edition blocked (no isolated-workload egress); trial workspace passed with 28 validated rows | `workspace_v2_smoke_trial_20260929.json`, `../docs/adr/native_v2_runtime_blocker.md` | passed (trial workspace) |
| Prophet identity | Local | Adapter audit at upstream commit `b2538be9d19abb191a2c8cf3306709e0cf7a2a0f` | Minimal attributed adaptation; 420/420 tuning trials | `../docs/adr/prophet_adapter.md`, `development_tuning_full_20260929/` | passed (development) |
| Development dashboard (Free Edition) | Workspace API | Dashboard definition export and API readback | Unpublished draft API-verified; visual inspection deferred by owner | `workspace_dashboard_paired_scores_20260929.json` | blocked (deferred) |
| Jobs unscheduled and single-run | Local + workspace | `tests/test_bundle_config.py`; `databricks bundle validate -t dev` | No schedule/trigger; `max_concurrent_runs: 1`; validation OK | `workspace_bundle_jobs_20260929.json` | passed |
| CI without secrets | Definition only | `.github/workflows/ci.yml` | No remote repository; workflow never executed | — | not run |
| Claim-to-row trace | Local + trial workspace | C01–C04 recomputed three ways: Python summary, SQL over persisted Delta cells, and plain CSV arithmetic on `series_scores.csv` | All match to 1e-12; claims marked verified (self-review accepted by owner, no independent human reviewer) | `claims.csv`, `trial/workspace_final_headline_sql_20260929.json` | passed |
| Final run persisted to Delta | Trial workspace | `scripts/persist_final.py` | 1/756/21,168/756 rows; zero missing/extra on readback | `trial/workspace_final_persist_20260929.json` | passed |
| Final dashboard | Trial workspace API | `scripts/deploy_final_dashboard.py` | Draft created; 5 datasets return expected populations; stored definition equals repository definition | `trial/workspace_final_dashboard_20260929.json` | passed (API) |
| Repeatability (3 series × 2 dev origins × 3 repeats) | Local + trial workspace | `scripts/repeatability.py` | v2 identical across repeats (points and bounds); Prophet points identical, interval bounds vary by up to ~15 requests (sampled uncertainty); 0 cached queries | `repeatability_20260929.json` | passed (Prophet interval noise disclosed) |
| Public asset and secret review | Local | `git grep` and `git log -S` over all commits for hosts, tokens, emails, workspace IDs, local paths | Free Edition host found in `capability_report.md` (38 commits); history rewritten with owner approval; `master` and tags now contain no host. Local pre-rewrite objects still need the owner's purge command before any mirror push | `../docs/history_rewrite.md` | passed for branch and tags |

## Known deviations and corrections

- Databricks CLI v0.280.0 Terraform download failed (`openpgp: key expired`); bundle deployment used `DATABRICKS_BUNDLE_ENGINE=direct`.
- The first `prepare_data` run (52045650234506) failed because serverless environment client 2 runs Python 3.11 and the package requires ≥3.12. The environment was changed to client 3; the failed attempt is retained here.

Do not erase failed attempts or replace blocked checks with fixture results.
