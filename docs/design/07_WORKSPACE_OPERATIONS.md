# Workspace, deployment and operations

## Default environment

The owner has an existing Databricks workspace and intends to use Free Edition. Use it; do not require a paid workspace or redesign around a different platform.

Free Edition is serverless-only, currently documents one small SQL warehouse, up to five concurrent job tasks and usage quotas, and may restrict outbound domains. Implement within those constraints; actual workspace capability checks are authoritative. [Free Edition limits](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations)

No workspace was accessed during creation of this planning package. API authentication, preview access, cloud runtime compatibility and dashboard deployment remain implementation checks.

## One-time readiness report

Record workspace cloud/edition, usable catalog and schema, SQL warehouse ID, available authentication method, package/runtime versions, ability to create project tables, bundle support, dashboard deployment and access to the NYC source. Use a project schema in an existing permitted catalog; do not assume catalog-creation rights.

Try local CLI OAuth through a supported environment. If corporate CLI use is blocked, use an allowed personal environment or supported SDK/notebook flow. Keep bundle definitions in the repository even if a temporary UI step is necessary; document the deployment gap rather than claim it was automated. Never bypass organization restrictions.

## Native SQL capability check

The official function documentation currently describes v2 as Beta, requiring Predictive AI Functions preview enrollment and a Pro or Serverless SQL warehouse. Pin `version => '2'`; omitting it currently selects v1. V2 uses a time-series foundation model and supports covariates/non-negative mode; its horizon boundary is right-exclusive. V2's documented signature does not include the v1 `parameters` or `seed` arguments. These facts must be rechecked at implementation time. [Databricks function reference](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_forecast)

Run this proposed smoke test in the actual SQL warehouse. It was not executed during planning:

```sql
WITH dates AS (
  SELECT explode(sequence(DATE '2024-01-01', DATE '2024-12-31', INTERVAL 1 DAY)) AS ds
), observed AS (
  SELECT ds, CAST(100 + 10 * dayofweek(ds) AS DOUBLE) AS y
  FROM dates
)
SELECT *
FROM ai_forecast(
  TABLE(observed),
  horizon => '2025-01-29',
  time_col => 'ds',
  value_col => 'y',
  frequency => 'D',
  prediction_interval_width => 0.8,
  positive_only => true,
  version => '2'
);
```

Expected: exactly 28 forecast dates, January 1–28, plus `y_forecast`, `y_lower`, `y_upper` outputs. Assert dates, non-finite values and interval ordering. Save sanitized error/query ID, duration and capability status. Confirm grouped inputs with two series next. A successful v1 invocation is not a v2 check.

If access is blocked, report the exact preview/permission error and supported enabling step. Continue local implementation. Never substitute a different model and label it v2. Obtain actual v2 evidence before releasing a three-way comparison.

## Job graph

Use four small job definitions or one parameterized job with stages:

1. `prepare_data`: retrieve or import aggregates, validate, create Silver.
2. `development`: tune/fit development forecasts, scores and frozen policy.
3. `benchmark`: execute final origins with resumable checkpoints, then evaluate.
4. `publish_results`: materialize serving views and generate evidence from an approved run.

Default max concurrent runs is one; submit model batches conservatively. The communication workstream can operate locally while cloud jobs run. Keep scheduling disabled. Do not make a dashboard refresh dependent on a model refit.

## Practical quota budget

Start with three series, one cutoff, five Prophet trials for smoke only. Final configuration caps at 25 series and 20 trials per series. With three tuning folds this implies at most 1,500 trial-fold fits, plus development and final refits. Twelve final origins produce at most 300 model/series/origin forecasts per candidate and 25,200 daily prediction rows across three candidates. Runtime is unknown until the pilot; do not promise this fits one day's quota.

After the pilot, estimate workload from measured fit/query durations and bound execution by available quota. Batch two final origins at a time initially. Persist tuning study results and selected parameters. Resume only missing work after interruption. Reducing final trials/series requires a pre-evaluation protocol revision; otherwise preserve settings and run across sessions.

Default per-model task wall timeout: 30 minutes for a small batch, configurable after measuring the pilot. Cap retry counts as specified in the protocol. Record timeouts as failures, not as a request to increase resources indefinitely.

## Source egress fallback

If the warehouse/notebook cannot access NYC Open Data, execute the same versioned extractor locally and upload the validated aggregate files into an accessible Unity Catalog volume or supported workspace ingestion path. Preserve payload hashes and manifests. This is an ordinary supported ingestion route, not an access-control workaround. Do not copy huge raw data into notebook literals.

## Configuration inputs

Use environment/config keys for `workspace_host`, `warehouse_id`, `catalog`, `schema`, `volume`, `experiment_id`, `snapshot_id`, `protocol_version`, `max_concurrency`, `timeouts` and `max_retries`. Credentials belong in supported authentication/secret mechanisms, never YAML. Validate SQL identifiers against allowed values before constructing SQL; bind ordinary scalar values where supported.

## Deployment

Proposed resource IDs: `prepare_data`, `development`, `benchmark`, `publish_results`, and `planning_dashboard`. Implement them before documenting these as runnable:

```bash
databricks bundle validate -t dev
databricks bundle deploy -t dev
databricks bundle run -t dev prepare_data
databricks bundle run -t dev development
databricks bundle run -t dev benchmark
databricks bundle run -t dev publish_results
```

Use serverless-compatible task/environment specifications validated against the installed CLI. Pin a working CLI version in CI after verification. Free Edition needs one real `dev` target; an optional `release` target may use a separate schema in the same workspace. Do not invent three enterprise environments for presentation value.

CI runs lint, meaningful tests, build, fixture-based contracts and document/link checks without cloud secrets. Cloud integration is opt-in with a supported identity and authorized workspace. Save test output. Deployment credentials must not be printed in logs.

## Runtime, cost and engineering burden

Measure extraction, preprocessing, tuning, final fitting/inference, evaluation and dashboard-query time separately. Log wall/queue/compute time where available, cold versus warm behavior, concurrency and retries. Native SQL batching and per-series Python fits have different execution boundaries: report batch throughput as well as series latency.

Free Edition's user bill of zero is not evidence that production compute costs zero. If billing/usage tables are unavailable, state monetary cost unavailable and report observed durations/quota use. A later paid-cost scenario must use actual SKU/region/rate sources, date, assumptions and uncertainty; do not infer money directly from seconds across different compute types.

Track active developer minutes by task category prospectively, starting now. Existing Prophet work is a sunk reusable asset, so this project cannot retrospectively prove total lifetime maintenance savings. Report new integration effort separately from upstream development. Count model-specific modules/config knobs/failure surfaces as descriptive evidence, not a proxy for guaranteed savings.

## Recovery and ongoing use

- Retry transient requests with the same keys and preserve attempts.
- Resume only uncompleted partitions/cells after quota reset.
- Keep latest-successful and latest-attempted run pointers separate.
- Roll back a dashboard/view release to a prior version without deleting benchmark history.
- Do not drop schemas or destroy bundles as routine cleanup.
- Export code and small evidence artifacts; Free Edition is not a permanent public demo guarantee.
- After release, a manual monthly rerun is sufficient. Recurring schedules are optional and require owner instruction.
