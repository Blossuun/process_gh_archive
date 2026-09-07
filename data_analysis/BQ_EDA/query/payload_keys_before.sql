-- Payload key structure on 2025-09-24, before the 2025-10 shrinkage.
--
-- Pairs with query/payload_keys_after.sql, which runs the same query against
-- 2025-11-12. Comparing the two shows which payload fields disappeared when
-- bytes per row fell from 3,683 to 1,199, a drop that event-type composition
-- cannot account for.
--
-- Both days are Wednesdays and neither is flagged in analysis/daily_volume.csv,
-- so day-of-week and partial-load effects are held constant.
--
-- COST: roughly 13.6 GB, measured. `payload` is the heavy column and there is
-- no way to read less of it here - the table is unpartitioned, and a WHERE
-- clause on `type` prunes no bytes in columnar storage.
--
-- TABLESAMPLE was tried and abandoned. It reduced the dry run estimate to
-- 626 MB but execution still demanded the full 13.56 GB, so sampling saved
-- nothing and only cost accuracy. Two lessons kept here: dry run estimates
-- are unreliable for sampled queries, and --max-bytes can be used as a free
-- probe, since a query that exceeds it reports the real requirement without
-- billing.
--
-- Run query/payload_keys_after.sql first. It covers the same ground at 4 GB,
-- so any mistake in the query shape surfaces there instead of here.
WITH enriched AS (
  SELECT
    type,
    COUNT(*) OVER (PARTITION BY type) AS type_events,
    ROUND(AVG(LENGTH(payload)) OVER (PARTITION BY type)) AS avg_payload_bytes,
    JSON_KEYS(
      PARSE_JSON(payload, wide_number_mode => 'round'),
      2,
      mode => 'lax recursive'
    ) AS key_paths
  FROM `githubarchive.day.20250924`
)
SELECT
  '20250924' AS day,
  type,
  key_path,
  COUNT(*) AS occurrences,
  ANY_VALUE(type_events) AS type_events,
  ROUND(COUNT(*) / ANY_VALUE(type_events) * 100, 1) AS coverage_pct,
  ANY_VALUE(avg_payload_bytes) AS avg_payload_bytes
FROM enriched, UNNEST(key_paths) AS key_path
GROUP BY type, key_path
ORDER BY type, key_path