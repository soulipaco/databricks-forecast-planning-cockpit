# Validation report — pre-release status

**Status:** Development interim, 29 September 2026. **No release candidate exists.** This table records the current state of each release check from actual local and workspace runs; it is not a release sign-off. The final 2025 evaluation has not been opened.

| Gate/check | Environment | Exact command or inspection | Actual outcome | Evidence reference | Status |
|---|---|---|---|---|---|
| Data snapshot reconciliation (2021–2024) | Local + workspace | `nyc311 ingest`, `materialize-development`; Silver Delta load and repeat merge | 48/48 monthly partitions reconciled; 30,681 series-days; first and repeat loads zero missing/extra/changed | `data_card.md`, `workspace_silver_load_20260929.json`, `workspace_silver_reload_20260929.json` | passed (development scope) |
| Silver reproducibility in workspace job | Workspace (serverless job) | `databricks bundle run -t dev prepare_data` | Rebuilt 30,681 rows, payload SHA-256 equal to the committed manifest | `workspace_bundle_jobs_20260929.json` (run 674664618781380) | passed |
| Data snapshot reconciliation (2025) | — | Not run | Holdout intentionally unopened until freeze | — | blocked (by protocol) |
| Protocol and leakage checks | Local | `uv run pytest -q` (leakage, split, selection-freeze tests) | 72 passed | test suite | passed (local) |
| Protocol freeze | Local + workspace | `nyc311 freeze --check-only …`; `bundle run development_gate` | Refused: `ai_forecast_v2` absent; 84/126 three-model development cells | `freeze_readiness_20260929.json`, `workspace_bundle_jobs_20260929.json` | blocked |
| Forecast grid and failures (development) | Local + workspace | Two-model development run and Delta persist/readback | 84/84 cells complete, 0 failed; 1/84/2,352/84 rows read back exactly twice | `development_two_model_full_20260929.json`, `workspace_development_two_model_persist*_20260929.json` | passed (two-model development only) |
| Forecast grid and failures (final) | — | Not run | Requires frozen protocol | — | blocked |
| Metric arithmetic and paired coverage | Local + workspace | `scripts/verify_development_predictions.py`; serving-view reconcile | All 84 score cells recomputed from 2,352 rows; 42/42 paired cells per model match in view | `development_prediction_arithmetic_20260929.json`, `workspace_development_score_reconcile_20260929.json` | passed (development only) |
| Native v2 identity | Workspace | `nyc311 smoke --config conf/local.yaml` | Managed runtime failed installing `onnxruntime==1.20.1` (PyPI timeouts); isolated-workload networking preview absent in Free Edition | `workspace_v2_smoke_20260929.json`, `../docs/adr/native_v2_runtime_blocker.md` | blocked |
| Prophet identity | Local | Adapter audit at upstream commit `b2538be9d19abb191a2c8cf3306709e0cf7a2a0f` | Minimal attributed adaptation; 420/420 tuning trials | `../docs/adr/prophet_adapter.md`, `development_tuning_full_20260929/` | passed (development) |
| Dashboard workspace inspection | Workspace API | Dashboard definition export and API readback | Unpublished draft API-verified; visual inspection deferred by owner | `workspace_dashboard_paired_scores_20260929.json` | blocked (deferred) |
| Jobs unscheduled and single-run | Local + workspace | `tests/test_bundle_config.py`; `databricks bundle validate -t dev` | No schedule/trigger; `max_concurrent_runs: 1`; validation OK | `workspace_bundle_jobs_20260929.json` | passed |
| CI without secrets | Definition only | `.github/workflows/ci.yml` | No remote repository; workflow never executed | — | not run |
| Claim-to-row trace | — | Not run | No release claims exist; `claims.csv` has headers only | `claims.csv` | blocked |
| Public asset and secret review | — | Not run | Required before publication | — | blocked |

## Known deviations and corrections

- Databricks CLI v0.280.0 Terraform download failed (`openpgp: key expired`); bundle deployment used `DATABRICKS_BUNDLE_ENGINE=direct`.
- The first `prepare_data` run (52045650234506) failed because serverless environment client 2 runs Python 3.11 and the package requires ≥3.12. The environment was changed to client 3; the failed attempt is retained here.

Do not erase failed attempts or replace blocked checks with fixture results.
