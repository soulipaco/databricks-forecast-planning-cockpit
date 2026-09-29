# Evidence

Every published number traces through `claim → table cell → metric calculation → prediction rows → run manifest → code/config/protocol → source snapshot` ([release gates](../docs/design/08_EVIDENCE_RELEASE.md)).

## Start here

| File | What it is |
|---|---|
| [`leaderboard.csv`](leaderboard.csv) | Final paired scores per model, with numerators and denominators |
| [`series_scores.csv`](series_scores.csv) | All 756 series × origin × model score cells |
| [`failures.csv`](failures.csv) | Every failed attempt (none in the final run) |
| [`runtime.csv`](runtime.csv) | Per-model wall and warehouse time, cache check |
| [`prediction_sample.csv`](prediction_sample.csv) | Rows behind the featured series |
| [`claims.csv`](claims.csv) | Each public claim with its calculation and review status |
| [`release_manifest.json`](release_manifest.json) | Release ID, run IDs and SHA-256 of every table |
| [`validation_report.md`](validation_report.md) | Each release gate: command, outcome, status |
| [`data_card.md`](data_card.md) | Source, extraction, selection and data limitations |

## Final benchmark (2025)

- `freeze_manifest.json`: protocol freeze, with hashes of the protocol, config, series manifest, tuning and development run.
- `final_local_20260929.json` and `final_native_v2_20260929.json`: raw runs (naïve and Prophet locally, `ai_forecast` v2 in a SQL warehouse), with all attempts, query IDs and every prediction.
- `final_three_model_20260929.json` and `final_three_model_summary_20260929.json`: combined grid and summary.
- `final_prediction_arithmetic_20260929.json`: independent recomputation of all 756 cells from 21,168 prediction rows.
- `repeatability_20260929.json`: three repeats on three series.
- `trial/`: Delta loads, persistence readback, SQL recomputation of the headline and the dashboard deployment in the trial workspace.

## Development (2024)

- `development_tuning_full_20260929/`: 20 Optuna trials per series on three inner origins (420 trials).
- `development_two_model_*`, `development_native_v2_full_20260929.json`, `development_three_model_*`: 2024 development runs used for the champion policy and the freeze.
- `freeze_readiness_*`: the freeze gate refusing on the two-model run, then passing on the three-model run.
- `development_slice_20260929.json`: an early three-series adapter check with fixed, untuned Prophet settings. It is used as a test fixture and is excluded from all claims.

## Native v2 access

`workspace_v2_smoke_20260929.json`, `v2_independent_recheck_20260929.json`, `v2_trial_workspace_smoke_20260929.json` and `workspace_v2_smoke_trial_20260929.json` record why v2 failed in Free Edition and what made it work in the trial workspace ([decision record](../docs/adr/native_v2_runtime_blocker.md)).

Workspace hosts, tokens and account identifiers are deliberately kept out of these files.
