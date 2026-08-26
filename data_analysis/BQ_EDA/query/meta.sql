SELECT
  table_id,
  TIMESTAMP_MILLIS(last_modified_time) AS last_modified,
  row_count,
  ROUND(size_bytes / POW(1024, 3), 2) AS size_gb
FROM `githubarchive.day.__TABLES__`
ORDER BY table_id DESC
LIMIT 10