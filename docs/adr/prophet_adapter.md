# Prophet adapter decision

Status: implemented locally; real Prophet fit and final tuning still need execution.

## Source audited

- Repository: <https://github.com/soulipaco/prophet-forecasting-mlops>
- Selected upstream commit: [`b2538be9d19abb191a2c8cf3306709e0cf7a2a0f`](https://github.com/soulipaco/prophet-forecasting-mlops/tree/b2538be9d19abb191a2c8cf3306709e0cf7a2a0f)
- License: MIT, copyright © 2026 Onur Uslu, as stated in upstream `LICENSE`.
- Actual callable imports inspected: `forecasting_project.prophet_model.build_model(parameters, holidays)` and `tune_and_fit(frame, holidays, window, tuning)`; `_trial_parameters(trial)` is internal. The package uses `prophet.Prophet`, `optuna`, and `pandas`.

## Decision

Use a small attributed adaptation in `src/nyc311_forecast/models/prophet_adapter.py`, rather than import the upstream model builder. No upstream source file is copied. The upstream builder hardcodes `growth="logistic"`, holiday and three arbitrary regressors plus `is_holiday`, monthly and custom weekly seasonalities, and a cap-dependent training frame. Its tuner uses a Prophet cross-validation RMSE objective with a different parameter search. A wrapper around those functions would retain those assumptions and violate the NYC protocol.

The adapter keeps the upstream fit/tune separation and uses the public Prophet and Optuna APIs. It fixes linear growth, weekly and yearly seasonality, disables daily seasonality, holidays and regressors, and requests an 80% interval. Tuning uses the three registered 2024 origins, each with the preceding 1,095 calendar days and a 28-day validation window. Optuna TPE seed is 42, with 20 trials per series for the primary benchmark. It minimizes pooled validation WAPE, rejects a zero denominator, and returns all trial records. The selected parameters are refit for each final origin; tuning time and per-origin fit/prediction time are separate fields. A five-trial call may be used only for a labeled smoke run.

The common model contract validates a sorted, gap-free history ending at the origin and the exact 28 future calendar dates. It retains raw point and interval values, clips negative values to zero for published predictions, does not round counts, and rejects non-finite or inverted intervals. No evaluation-window target is passed into a model fit. The `snaive7` parity fixture proves a seven-day calendar rather than weekday-only dates.

## Integration checks still required

Run the optional Prophet dependency in a compatible Python environment and record the resolved package versions. Execute at least one real seven-day-calendar fit, all saved tuning trials, and repeated development inference for interval variability. Do not claim final benchmark results from the synthetic contract tests.
