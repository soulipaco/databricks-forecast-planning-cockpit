-- Contract v1 table definitions. Render {{catalog}} and {{schema}} from
-- validated identifiers. Deployed to the authenticated project schema on 2026-09-29.
-- Logical uniqueness must be enforced by loaders/tests; Delta does not enforce it.

CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}.source_partitions (
  snapshot_id STRING NOT NULL, partition_id STRING NOT NULL,
  endpoint STRING, query_hash STRING, extracted_at TIMESTAMP,
  payload_hash STRING, aggregate_rows BIGINT, source_count BIGINT,
  grouped_count BIGINT, status STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}.daily_requests (
  snapshot_id STRING NOT NULL, series_id STRING NOT NULL, ds DATE NOT NULL,
  borough STRING, problem_family STRING, y BIGINT,
  is_zero_filled BOOLEAN, quality_status STRING, mapping_version STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}.series_manifest (
  experiment_id STRING NOT NULL, series_id STRING NOT NULL,
  selection_rank INT, inclusion_status STRING, reason STRING,
  positive_days INT, median_daily_count DOUBLE, active_span_days INT,
  selection_data_hash STRING, mapping_hash STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}.forecast_runs (
  run_id STRING NOT NULL, experiment_id STRING, snapshot_id STRING,
  protocol_hash STRING, config_hash STRING, code_sha STRING, upstream_sha STRING,
  environment STRING, started_at TIMESTAMP, ended_at TIMESTAMP,
  status STRING, supersedes_run_id STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}.forecast_attempts (
  run_id STRING NOT NULL, model_id STRING NOT NULL, origin DATE NOT NULL,
  series_id STRING NOT NULL, attempt_no INT NOT NULL,
  status STRING, error_class STRING, safe_error_message STRING,
  query_id STRING, queue_seconds DOUBLE, compute_seconds DOUBLE,
  wall_seconds DOUBLE, retry_reason STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}.forecast_values (
  run_id STRING NOT NULL, model_id STRING NOT NULL, origin DATE NOT NULL,
  series_id STRING NOT NULL, ds DATE NOT NULL, lead_day INT,
  prediction DOUBLE, lower DOUBLE, upper DOUBLE, interval_level DOUBLE,
  raw_prediction DOUBLE, raw_lower DOUBLE, raw_upper DOUBLE,
  transformed BOOLEAN, is_fallback BOOLEAN
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}.evaluation_cells (
  run_id STRING NOT NULL, model_id STRING NOT NULL, origin DATE NOT NULL,
  series_id STRING NOT NULL, horizon_days INT NOT NULL,
  n_expected INT, n_actual INT, n_predictions INT, paired_status STRING,
  abs_error_sum DOUBLE, actual_sum DOUBLE, signed_error_sum DOUBLE,
  mase_denominator DOUBLE, interval_n INT, interval_hits INT,
  interval_width_sum DOUBLE, interval_score_sum DOUBLE
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}.champion_policy (
  policy_id STRING NOT NULL, series_id STRING NOT NULL,
  selected_model_id STRING, selected_on_data_through DATE,
  development_run_id STRING, reason STRING, tolerance_config_hash STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}.capacity_assumptions (
  scenario_id STRING NOT NULL, series_id STRING NOT NULL, ds DATE NOT NULL,
  capacity_requests DOUBLE, assumption_source STRING,
  is_illustrative BOOLEAN, version STRING
) USING DELTA;

CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}.release_claims (
  release_id STRING NOT NULL, claim_id STRING NOT NULL, `text` STRING,
  source_artifact STRING, calculation_reference STRING,
  evidence_run_id STRING, review_status STRING
) USING DELTA;
