-- P05 scaffold, contract v1. Render {{catalog}} and {{schema}} from validated
-- SQL identifiers before execution. This file has not been run in Databricks.
-- All dashboard datasets must bind run_id and origin; views alone are not a
-- permission or freshness boundary. No view invokes a forecasting model.

CREATE OR REPLACE VIEW {{catalog}}.{{schema}}.v_forecast_detail AS
SELECT
  fv.run_id, fv.model_id, fv.origin, fv.series_id, fv.ds, fv.lead_day,
  fv.prediction, fv.lower, fv.upper, fv.interval_level, fv.is_fallback,
  dr.y AS actual_requests, dr.borough, dr.problem_family,
  fr.snapshot_id, fr.status AS run_status
FROM {{catalog}}.{{schema}}.forecast_values AS fv
JOIN {{catalog}}.{{schema}}.forecast_runs AS fr
  ON fr.run_id = fv.run_id
LEFT JOIN {{catalog}}.{{schema}}.daily_requests AS dr
  ON dr.snapshot_id = fr.snapshot_id
 AND dr.series_id = fv.series_id
 AND dr.ds = fv.ds;

-- Preserve each vintage and scenario. A dashboard query must bind run_id,
-- origin, series_id, policy_id and scenario_id before summing dates.
CREATE OR REPLACE VIEW {{catalog}}.{{schema}}.v_planning_gap AS
SELECT
  fv.run_id, fv.origin, fv.series_id, fv.ds, fv.model_id,
  cp.policy_id, ca.scenario_id,
  fv.prediction AS forecast_requests,
  ca.capacity_requests,
  fv.prediction - ca.capacity_requests AS net_gap_requests,
  greatest(fv.prediction - ca.capacity_requests, 0) AS daily_shortage_requests,
  CASE WHEN fv.upper IS NULL THEN NULL ELSE fv.upper > ca.capacity_requests END AS possible_pressure,
  CASE WHEN fv.lower IS NULL THEN NULL ELSE fv.lower > ca.capacity_requests END AS lower_bound_above_capacity,
  ca.is_illustrative,
  ca.assumption_source
FROM {{catalog}}.{{schema}}.forecast_values AS fv
JOIN {{catalog}}.{{schema}}.champion_policy AS cp
  ON cp.series_id = fv.series_id
 AND cp.selected_model_id = fv.model_id
JOIN {{catalog}}.{{schema}}.capacity_assumptions AS ca
  ON ca.series_id = fv.series_id
 AND ca.ds = fv.ds;

-- Raw sufficient statistics, not an average of percentages. A dashboard
-- dataset must form complete paired populations before aggregating this view.
CREATE OR REPLACE VIEW {{catalog}}.{{schema}}.v_model_leaderboard_cells AS
SELECT
  ec.run_id, ec.model_id, ec.origin, ec.series_id, ec.horizon_days,
  ec.n_expected, ec.n_actual, ec.n_predictions,
  ec.abs_error_sum, ec.actual_sum, ec.signed_error_sum,
  CASE WHEN ec.actual_sum = 0 THEN NULL
       ELSE ec.abs_error_sum / ec.actual_sum END AS cell_wape
FROM {{catalog}}.{{schema}}.evaluation_cells AS ec;

-- Attempts remain visible even if a later retry succeeds. Safe error text
-- comes from the contract's sanitized field, never from request headers.
CREATE OR REPLACE VIEW {{catalog}}.{{schema}}.v_run_health AS
SELECT
  fa.run_id, fa.model_id, fa.origin, fa.series_id, fa.attempt_no,
  fa.status, fa.error_class, fa.safe_error_message, fa.retry_reason,
  fa.query_id, fa.queue_seconds, fa.compute_seconds, fa.wall_seconds
FROM {{catalog}}.{{schema}}.forecast_attempts AS fa;
