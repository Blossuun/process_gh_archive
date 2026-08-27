-- Full inventory of githubarchive day tables.
-- Metadata-only query: costs 0 bytes.
-- Purpose: confirm the available date range and spot gaps or size anomalies
--          before deciding which dates to sample for the field catalog.
SELECT
  table_id,
  TIMESTAMP_MILLIS(creation_time) AS created_at,
  TIMESTAMP_MILLIS(last_modified_time) AS last_modified,
  row_count,
  size_bytes
FROM `githubarchive.day.__TABLES__`
WHERE type = 1  -- exclude views such as `yesterday`
ORDER BY table_id