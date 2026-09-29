# Benchmark protocol v1.0

Status: proposed, to be frozen after the vertical slice and before final evaluation. All choices below are experimental design decisions. Register deviations and their reasons; never silently overwrite the protocol after inspecting final results.

## Experiment matrix

| Dimension | Primary experiment |
|---|---|
| Target | Daily service-request count |
| Series | Frozen borough × problem-family manifest |
| Candidates | `snaive7`, `prophet_tuned`, `ai_forecast_v2` |
| Forecast length | 28 calendar days |
| Reports | Lead days 1–7 and 1–28; also 8–14 and 15–28 diagnostics |
| Training | Last 1,095 calendar days through each origin, inclusive |
| Inputs | Identical observed target history and dates; no external covariates |
| Intervals | One nominal 80% interval for Prophet and native SQL |
| Final origins | Twelve month-end cutoffs, 2024-12-31 through 2025-11-30 |
| Test year | Forecast target dates in 2025, through 2025-12-28 |
| Primary score | Median series-level WAPE for the 28-day horizon |
| Supporting scores | Pooled WAPE, MASE, signed bias, interval coverage/width, reliability and runtime |

The 7-day score reuses the first seven predictions of the same 28-day invocation. This compares a shared operational forecast, not models separately optimised for each horizon.

## Development and freeze sequence

1. Select series from 2021–2023, using `02_DATA_SPEC.md`.
2. Tune Prophet independently for each series on three inner origins: 2024-01-31, 2024-05-31 and 2024-09-30. Each validation window is the next 28 days; each fit uses only the preceding 1,095 days.
3. Evaluate frozen candidate configurations at development origins 2024-10-31 and 2024-11-30. Use these for the provisional champion policy, implementation debugging and runtime estimates. Two origins are limited evidence; state this.
4. Freeze protocol, selected series, transforms, software, hyperparameters, retry policy and reporting logic in a signed/hash manifest and Git commit/tag.
5. Run the twelve final origins. Refitting on observations known by each origin is allowed, including earlier 2025 observations. Changing settings based on 2025 performance is not.

Use explicit cutoffs, never random train/test splits. A model adapter receives a bounded history frame, not the full dataset plus a promise to ignore future rows. Assert `max(train_date) == origin` and all future targets passed to covariate mode are null. Prophet's documentation demonstrates cutoff-based evaluation; this project's split is intentionally specified above. [Prophet diagnostics](https://facebook.github.io/prophet/docs/diagnostics.html)

## Candidate definitions

### Weekly seasonal naïve

Repeat the final seven observed days. For origin `c` and lead `h` in 1…28:

`prediction(c+h) = y[c - 6 + ((h - 1) mod 7)]`.

This avoids accidentally using actual values from the evaluation window for lead 8 onward. No fitting, tuning or default interval. Report interval measures as N/A, not zero. A train-only residual interval is a separately named extension.

### Tuned Prophet

Audit the existing package before integration. Reuse its stable model builder/tuning capabilities through a pinned adapter where suitable; ensure a single target, seven-day calendar, daily dates and a 28-day horizon. Do not inherit weekday-only closure logic, three-calendar-month horizon, unrelated targets or logistic caps.

Default primary search: linear growth, weekly seasonality enabled, yearly seasonality enabled, daily seasonality disabled, no holidays, no external regressors. Seed the Optuna sampler at 42 and save all trials. Use 20 trials per series; parameters: `changepoint_prior_scale` log-uniform 0.001–0.5; `seasonality_prior_scale` log-uniform 0.01–10; `seasonality_mode` additive or multiplicative. Keep other settings explicit and fixed. Objective is pooled WAPE across the three inner 28-day validations. An undefined denominator fails the trial rather than scoring zero.

Select one parameter set per series and refit at each final origin. Include the original tuning cost separately from subsequent fitting/prediction cost. If a reduced 5-trial configuration is needed for the vertical slice, label it smoke-only. Do not call it the final tuned benchmark.

Retain raw Prophet predictions and apply the common non-negative publication policy below. Record seeds where supported; repeatability of intervals must be checked rather than promised.

### Native SQL

Use the explicit version and smoke-test recipe in `07_WORKSPACE_OPERATIONS.md`. The primary run has no holiday or external covariate enrichment. Keep native SQL inference bounded to the same history and origin. Convert the native output into the shared adapter contract, including query ID and invocation timing.

There is no requirement to recreate the managed model's internal architecture. Log the documented version selector, execution timestamp and observable service/runtime metadata. If internal model weights or pretraining data are undisclosed, record them as unavailable.

## Non-negative policy

Counts cannot be negative. Require native non-negative mode. For all point forecasts and bounds, retain raw outputs then apply `max(0, value)` in the shared publication/scoring transformation. Do not round fractional expectations. Validate lower ≤ upper. Reject non-finite values and malformed intervals; do not manufacture missing bounds. Report how many outputs changed under the transformation.

## Exact metric definitions

Let `e = prediction - actual`, so positive bias is overforecasting. Evaluate each defined horizon over its expected date grid.

| Metric | Calculation and policy |
|---|---|
| WAPE | `sum(abs(e)) / sum(abs(actual))`; undefined when denominator is zero |
| Primary macro WAPE | First calculate each series' WAPE pooled over its twelve origins, then take the median across series |
| Pooled WAPE | Sum absolute errors over all series/origins divided by sum actuals; high-volume series have more influence |
| MASE | Per series/origin MAE divided by `mean(abs(train[t] - train[t-7]))` on that origin's history; denominator zero → N/A; report median valid cells and valid count |
| Signed bias | `sum(prediction-actual) / sum(actual)`; positive means excess planned demand |
| Coverage | Fraction of actuals inside the reported interval, inclusive; valid paired intervals only |
| Interval width | Mean upper-minus-lower; also divide total width by total actual volume for a scale-relative view |
| Interval score | For alpha=0.2: width plus `(2/alpha)*(lower-y)` below lower or `(2/alpha)*(y-upper)` above upper; otherwise width |
| Relative WAPE gain | `(baseline_WAPE - model_WAPE) / baseline_WAPE`; baseline zero → N/A |
| Failure rate | Unsuccessful expected series-origin attempts / all expected series-origin attempts after the fixed retry policy |

Store numerator, denominator and sample size alongside ratios. Never average percentages without specifying the weighting. A change from 20% WAPE to 18% is 2 percentage points and 10% relative improvement. Do not call `1-WAPE` universal forecast accuracy.

## Failures and fair comparisons

Preconstruct the complete series × origin × model × date grid. An output with fewer than 28 distinct expected dates, duplicate dates or invalid values is not a complete forecast.

- Headline comparison uses the common complete series-origin cells shared by all three candidates. Display expected and paired counts directly beside it.
- Require at least 95% of planned series-origin cells to be complete for every model for an unrestricted primary comparison. Below that, publish partial results and reliability limitations prominently; do not claim a complete benchmark.
- Show each model's full-coverage statistics separately, never compare them as if their populations were identical.
- A failed primary model may use seasonal naïve for a planning demo, explicitly labelled as fallback. Those rows never enter that model's benchmark score.
- Retry only transient errors, at most twice after the initial model attempt, using the same inputs. Keep all attempts and total time. Data/schema errors do not get blind retries.
- If a code bug forces a corrected final run, preserve the first artifacts, document the bug and rerun every affected candidate/cell under the corrected version. Do not patch only losing cases.

## Decision policy, decided before final scores

For the portfolio, define native SQL as *practically competitive* when its primary WAPE is no more than 5% relatively worse than Prophet, its absolute signed bias is no more than 2 percentage points worse, and successful-cell coverage is at least 95%. These margins are illustrative engineering choices, not NYC requirements or statistical equivalence tests.

Also show interval reliability against nominal 80%; a 70–90% observed range is a diagnostic flag band, not a confidence test. A point-error tie does not excuse badly misleading intervals.

For a provisional per-series planning champion, use only the two development origins. Qualifying requires both complete origin forecasts. Find the lowest WAPE among qualifying candidates, then retain those no more than 5% relatively worse. Choose the simplest retained candidate in the fixed order: naïve, native SQL, Prophet. If the best WAPE is zero, only zero-WAPE candidates enter the tie-break. Save the decision and supporting scores. If none qualify, show unavailable/fallback. This point-forecast selection policy does not require a baseline interval; show unavailable uncertainty when the baseline wins. Evaluate the frozen policy on 2025 alongside the individual models. Any champion reselected from all 2025 results is a later production choice and has no independent 2025 performance claim.

## Robustness and uncertainty

Report paired score differences by series and origin, not only one overall number. A descriptive paired bootstrap can resample whole series with all their origins (2,000 resamples, fixed seed); disclose that series share city-wide shocks and these intervals do not establish independent population-wide significance. No universal winner or equivalence claim from one dataset.

Repeat the same development inference three times on three series to measure observable native/Prophet variability. Separate queue/startup from query/fit time where instrumentation permits; mark unsupported timing fields unavailable. Do not compare cached SQL result retrieval against a fresh Python fit. Verify query execution metadata or mark the timing unsuitable.

Public historical data might overlap with a foundation model's training corpus. Its corpus is not established here. Call this an application benchmark with leakage controls in the project pipeline; do not claim a pretraining-clean evaluation. As a stretch, register a prospective 28-day forecast before outcomes arrive, then score it later without replacing the original predictions.

## Secondary experiments, only after primary freeze

Calendar enrichment: one separately versioned experiment with the same future-known holiday indicator supplied to both Prophet and native SQL; log the holiday calendar and feature hash. This is cleaner for feature parity than assuming two built-in holiday implementations are identical. Seasonal naïve remains unchanged.

Weather: excluded from v1. Prophet regressors require future values, so historical-only weather is not automatically an equivalent input across approaches. Future weather experiments need archived forecasts available at each origin, or an explicit oracle label. Never give observed future weather to the headline benchmark.

An 84-day horizon, 2018–2020 regime stress test, interval calibration and alternative training windows each require a separately identified protocol. Do not multiply experiments until an appealing story appears.

## Registered deviations before freeze

Recorded on 2026-09-29, after the 2024 development runs and before any 2025 data was retrieved.

| ID | Deviation | Reason | Evidence |
|---|---|---|---|
| D1 | Native v2 runs in a non-Free-Edition Databricks trial workspace; naïve and Prophet run locally. Both read the same Silver payload (SHA-256 `31c0f356…`), verified by exact Delta readback in each workspace. | Free Edition cannot enable networking for isolated SQL workloads, which v2's managed runtime needs. | `docs/adr/native_v2_runtime_blocker.md`, `evidence/trial/workspace_silver_load_20260929.json` |
| D2 | v2 `horizon` is `origin + 28 days`, not `origin + 29`. The adapter still requires exactly leads 1–28 and fails on any other row count. | v2 returned the horizon date despite the documented right-exclusive boundary. | `docs/adr/native_v2_horizon.md` |
| D3 | Each native query text carries a unique run/series/origin comment, and query-history metadata must show `result_from_cache = false`. | Protocol forbids comparing cached SQL retrieval with fresh fits. | `evidence/development_native_v2_full_20260929.json` (`queries_from_cache: 0`) |

The development results were inspected before this registration. None of D1–D3 changes a model setting, metric, series or tuning choice.
