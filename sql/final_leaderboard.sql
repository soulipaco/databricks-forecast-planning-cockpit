-- Protocol v1 headline on complete three-model paired cells for one bound run.
-- Reads stored evaluation cells only; never invokes a model.
WITH paired AS (
  SELECT series_id, origin
  FROM evaluation_cells
  WHERE run_id = :run_id AND paired_status = 'complete'
  GROUP BY series_id, origin
  HAVING COUNT(DISTINCT model_id) = 3
), cells AS (
  SELECT ec.*
  FROM evaluation_cells AS ec
  JOIN paired AS p ON p.series_id = ec.series_id AND p.origin = ec.origin
  WHERE ec.run_id = :run_id
), series_wape AS (
  SELECT model_id, series_id, SUM(abs_error_sum) / SUM(actual_sum) AS wape
  FROM cells GROUP BY model_id, series_id
), medians AS (
  SELECT model_id, percentile_cont(0.5) WITHIN GROUP (ORDER BY wape) AS median_series_wape
  FROM series_wape GROUP BY model_id
), pooled AS (
  SELECT model_id,
    SUM(abs_error_sum) / SUM(actual_sum) AS pooled_wape,
    SUM(signed_error_sum) / SUM(actual_sum) AS signed_bias,
    SUM(interval_hits) / NULLIF(SUM(interval_n), 0) AS interval_coverage,
    COUNT(*) AS paired_cells
  FROM cells GROUP BY model_id
)
SELECT m.model_id, m.median_series_wape, p.pooled_wape, p.signed_bias,
  p.interval_coverage, p.paired_cells
FROM medians AS m JOIN pooled AS p USING (model_id)
ORDER BY m.median_series_wape
