# Evidence workspace

This directory contains a verified local [data card](data_card.md), workspace validation records and release templates. No three-model benchmark result is recorded. `development_smoke.json` and `development_slice_20260929.json` are adapter integration checks with fixed, untuned Prophet settings; both are excluded from benchmark claims. The latter covers the two registered 2024 development origins for three series and stores all local forecast rows, scores and attempts. Do not interpret an empty CSV as a zero result or a passed gate.

`development_tuning_full_20260929/` holds 21 per-series checkpoints with 20 completed Prophet trials each, using three 2024 inner origins. `development_two_model_full_20260929.json` contains the complete 2024 development output for weekly naive and tuned Prophet: 84 model cells and 2,352 forecast rows. `development_two_model_diagnostic_20260929.json` contains paired ratio-of-sums statistics and the actual/error numerators; `workspace_development_score_reconcile_20260929.json` verifies those sums in the serving view. `workspace_development_two_model_persist_20260929.json` and its repeat record exact Delta readback. `workspace_dashboard_development_20260929.json` records the unpublished dashboard API check. Every one of these is explicitly a **two-model, 2024 development artifact**, not the three-model benchmark or 2025 holdout evaluation.

`development_prediction_arithmetic_20260929.json` records an independent recomputation of absolute error, actual volume, signed error and interval measures from all 2,352 prediction rows against the 84 stored score cells. The source is `scripts/verify_development_predictions.py`.

`workspace_dashboard_paired_scores_20260929.json` is the latest unpublished dashboard API verification: both models have 42 paired 2024 development cells, and its score dataset agrees with the local and workspace numerator/denominator evidence. The older `workspace_dashboard_development_20260929.json` preserves the preceding coverage-only draft.

For a release, trace each public claim through `claim → chart/table cell → metric calculation → prediction rows → run manifest → code/config/protocol → source snapshot`. The required artifacts and gates are defined in [08_EVIDENCE_RELEASE.md](../08_EVIDENCE_RELEASE.md). Only publish result assets after the release run and independent review have been completed.

## Claims ledger

`claims.csv` starts with headers only. Add one row for each discrete claim before using it in a README, chart, post or demo. Keep `status` as `draft` until the cited calculation has been reproduced and a reviewer has inspected the full population and limitations. Record the same claim ID in the asset source or caption. Unsupported claims stay out of public copy.

Fields: `claim_id`, `wording`, `claim_type`, `evidence_artifact`, `calculation_reference`, `release_id`, `run_id`, `population_and_denominator`, `limitations`, `reviewer`, `status`, `reviewed_at_utc`.

Examples of claims requiring evidence: relative WAPE differences, series wins, runtime comparisons, engineering effort, dashboard behavior and capacity effects. The [release guide](../08_EVIDENCE_RELEASE.md) gives safe pre-evidence wording.

## Data and validation records

`data_card.md` records the real 2021–2024 development source and Silver checks. `validation_report.md` records the current pre-release status of each check; it is not a release sign-off. `freeze_readiness_20260929.json` is the refused freeze check, and `workspace_bundle_jobs_20260929.json` records the bundle deployment and serverless job runs (Silver reproduction passed; freeze gate blocked). Mark checks `passed`, `failed` or `blocked` with exact evidence; never turn an unavailable workspace check into a pass. Keep private workspace URLs, tokens and account details out of these public files.
