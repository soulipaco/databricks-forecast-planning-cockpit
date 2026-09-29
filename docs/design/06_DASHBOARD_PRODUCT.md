# AI/BI dashboard and planning experience

## Product promise

Within one minute, a reader can answer: what demand is forecast, how reliable is it, which model was used, and how does it compare with an explicit capacity assumption?

The native dashboard is the working product. Public readers get screenshots, a short recording, the same aggregate evidence and the methodology without a workspace login. Do not assume anonymous dashboard access is supported or enabled.

## Page 1: planning overview

Default to one selected series and one origin, with a clearly visible historical-backtest badge. Show borough, problem family, forecast vintage, data-through date, model and fallback status. Use 28 days of forecast and enough recent actuals for context.

Main chart: actual and forecast lines, an interval ribbon if supported by the available visualization, and an assumed capacity reference. If native ribbon support is unsuitable, use a supported range view or lower/upper series with clear labels. Do not fake a visualization type in JSON.

Cards: forecast requests over the selected horizon, assumed capacity, cumulative net gap, number of daily overloads, and data freshness. Distinguish `sum(max(0, demand-capacity))` from `max(0, sum(demand-capacity))`; daily shortages cannot always be offset by unused capacity on other days.

## Capacity assumptions

The source has no processing capacity or handling-time measurement. Default illustration: constant daily capacity equal to the mean of the last 28 observed training days, multiplied by a user-controlled factor initially 1.0. Derive it only from dates ≤ origin. Label it **Illustrative capacity, not NYC staffing data** next to the chart.

For a selected series/date:

- `net_gap = point_forecast - capacity_requests`.
- `possible_pressure = upper_bound > capacity_requests`, only if an interval exists.
- `likely_pressure_under_lower_bound = lower_bound > capacity_requests` is a descriptive threshold flag, not a calibrated probability.

Do not translate request counts into headcount by assuming one request equals one telephone call. A later workload conversion needs measured handling time, work mix and shrinkage. Any user-supplied conversion must stay visibly hypothetical.

## Page 2: model comparison

Show each model's 28-day median series WAPE, pooled WAPE, MASE, signed bias, success rate and runtime. Display paired versus expected cell counts in the heading. Allow a 7-day slice and borough/family filters. Avoid one opaque composite score.

Include a per-series paired-error difference chart: native SQL minus Prophet, labelled so positive means native SQL has higher error. A separate comparison against seasonal naïve prevents the strongest-looking model being declared useful when both lose to the baseline.

Intervals: show observed coverage against the 80% nominal reference and typical width. Mark naïve intervals N/A. Lead-time diagnostics must distinguish day 1–7, day 8–14 and day 15–28 from cumulative horizons.

## Page 3: reliability and exceptions

Rows identify missing source partitions, failed forecasts, low coverage, long zero runs, excessive bias and quota/access errors. Filter by run and model. Include safe error text, attempt count and next action. Never show raw credentials or sensitive request headers.

For ongoing monitoring, compare arriving actuals with stored prediction vintages; exclude future dates without actuals. Do not count an absent actual as zero. Initial alerts remain dashboard flags, not unsolicited email or Slack automation.

## Page 4: method and provenance

Show the data source, retrieval date, frozen series criteria, training window, origins, metrics, version, snapshot/config hashes and link to the methodology. Explain the current-snapshot limitation and potential foundation-model pretraining overlap. Provide a small model-work versus shared-work table.

## Optional page 5: scenarios

First scenario is a capacity-factor change with demand held fixed; label it a capacity scenario, not a new forecast. A demand uplift slider is a sensitivity calculation, not model evidence. Only label a scenario as covariate-conditioned forecasting if a separately executed and stored model run produced it. Do not infer causal impact from association with holidays or weather.

## Data and query constraints

All pages read materialized results or governed views. Changing a filter must never call `ai_forecast` or fit Prophet. Every query constrains run/origin, avoids multiple vintages double counting, and preserves metric numerators/denominators. Do not average WAPE values across arbitrary filtered groups.

When showing totals, sum point forecasts only. Do not sum lower/upper bounds as though that preserves aggregate coverage. Label the total as a sum of individual forecasts, with aggregate uncertainty unavailable.

## Layout and visuals

Use a light background, dark text and generous white space. Keep actuals charcoal, seasonal naïve orange, Prophet green and native SQL (`ai_forecast` v2) blue consistently across the dashboard and the repository figures. Use labels and line styles alongside color. Every figure needs units, date range, model labels, evidence run ID and a short takeaway. A practical result chart should be the focal point; stack logos and architectural decoration are secondary.

The public result card should survive viewing at approximately 360 px wide. Limit it to one main comparison and one limitation; move detail to the next slide or README. No generated images for numerical charts.

## Dashboard as code

Databricks bundle resources support dashboard definitions referenced by `file_path`; exported dashboard files use `.lvdash.json`. Validate against the installed CLI's schema and a real exported minimal dashboard before extending it. [Bundle dashboard resources](https://docs.databricks.com/aws/en/dev-tools/bundles/resources#dashboard)

Recommended implementation: create/export a minimal native dashboard, version it, substitute environment identifiers through a deterministic build step, deploy the rendered definition through the bundle, then inspect it. If UI work is initially necessary to discover a schema, export the result immediately. Keep the tracked definition authoritative afterwards.

## Product acceptance

A reviewer must successfully change series, origin and horizon; reconcile one displayed metric to the underlying score file; see a failed series and an illustrative-capacity label; inspect a historical vintage without contamination from newer runs; and verify that refresh causes no model invocation. Test empty selections and missing interval data. JSON validity alone does not establish a working dashboard.
