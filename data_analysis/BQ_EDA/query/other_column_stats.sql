-- The `other` column, before and after the 2025-10 payload shrinkage.
--
-- `other` is a STRING column in the day-table schema that this EDA has never
-- looked at. Byte accounting says the payload fields that vanished did not
-- move here in bulk: everything outside `payload` grew by only 70 bytes per
-- row (202 -> 272) while payload lost 2,554. This query checks the remaining
-- 70 bytes and establishes whether `other` holds anything worth keeping.
--
-- Scans `other` only. TABLESAMPLE is not used - it was measured to reduce the
-- dry run estimate without reducing bytes billed, so it costs accuracy for
-- nothing. UNION ALL over two plain tables is fine; the restriction only
-- applies to sampled ones.
--
-- Run with a low --max-bytes first. If `other` turns out to be large, the
-- query fails before billing and reports the real requirement.
SELECT
  '20250924' AS day,
  COUNT(*) AS rows_total,
  COUNTIF(other IS NOT NULL) AS other_present,
  ROUND(COUNTIF(other IS NOT NULL) / COUNT(*) * 100, 2) AS present_pct,
  ROUND(AVG(LENGTH(other))) AS avg_other_bytes,
  MAX(LENGTH(other)) AS max_other_bytes,
  COUNT(DISTINCT other) AS distinct_values
FROM `githubarchive.day.20250924`
UNION ALL
SELECT
  '20251112' AS day,
  COUNT(*) AS rows_total,
  COUNTIF(other IS NOT NULL) AS other_present,
  ROUND(COUNTIF(other IS NOT NULL) / COUNT(*) * 100, 2) AS present_pct,
  ROUND(AVG(LENGTH(other))) AS avg_other_bytes,
  MAX(LENGTH(other)) AS max_other_bytes,
  COUNT(DISTINCT other) AS distinct_values
FROM `githubarchive.day.20251112`
ORDER BY day