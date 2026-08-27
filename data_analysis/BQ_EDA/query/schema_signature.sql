-- Group every githubarchive day table by its column signature.
-- Reveals how many distinct table-level schemas exist and where the
-- boundaries fall, without scanning any payload data.
--
-- Cost: INFORMATION_SCHEMA queries are billed at a 10 MB minimum.
WITH signature AS (
  SELECT
    table_name,
    STRING_AGG(
      column_name || ' ' || data_type,
      ', '
      ORDER BY ordinal_position
    ) AS schema_signature
  FROM `githubarchive.day.INFORMATION_SCHEMA.COLUMNS`
  WHERE REGEXP_CONTAINS(table_name, r'^\d{8}$')  -- exclude the `yesterday` view
  GROUP BY table_name
)
SELECT
  schema_signature,
  COUNT(*) AS table_count,
  MIN(table_name) AS first_table,
  MAX(table_name) AS last_table
FROM signature
GROUP BY schema_signature
ORDER BY first_table