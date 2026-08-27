-- Hourly event distribution for selected days.
--
-- GH Archive publishes one file per hour; a BigQuery day table is the union of
-- 24 of them. A day table can therefore exist while some hours never loaded,
-- which table-level checks cannot see. Counting events per hour exposes it.
--
-- Scans `created_at` only, never `payload`, so the cost stays low.
--
-- Group A - suspect days, taken from analysis/table_inventory_report.md.
--   These border a gap or were created late, so ingestion is known to have
--   struggled there. They double as a positive control: if the hourly view
--   finds nothing here, the method itself is too weak to trust elsewhere.
--
--     20180403 20180404 20180405  created 1-2 days late, no missing table
--     20200821 20200823           either side of the 2020-08-22 gap
--     20210507 20210509 20210512  around the 2021-05-08 and 05-10~11 gaps
--                                 (0509 sits between two gaps)
--     20210825 20210827           either side of the 2021-08-26 gap
--     20211025 20211029           either side of the 2021-10-26~28 gap
--
-- Group B - reference days, all Wednesdays so that day-of-week does not
--   confound comparisons between them.
--
--     20210915  control, just before the 2021-10 volume drop
--     20211013  inside the 2021-10 drop (-54% events per day)
--     20240918  control, peak year
--     20250917  just before the 2025-10 bytes-per-row collapse
--     20251112  just after it
--     20260415  inside the ongoing 2026 decline
--     20260715  most recent full month of that decline
--
-- The `day.20*` prefix excludes the `yesterday` view, which cannot be read
-- through a wildcard. _TABLE_SUFFIX is therefore the table id minus '20'.
SELECT
  CONCAT('20', _TABLE_SUFFIX) AS day,
  EXTRACT(HOUR FROM created_at) AS hour,
  COUNT(*) AS events,
  ROUND(
    COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY _TABLE_SUFFIX) * 100,
    2
  ) AS share_pct
FROM `githubarchive.day.20*`
WHERE _TABLE_SUFFIX IN (
  -- group A: suspect days
  '180403', '180404', '180405',
  '200821', '200823',
  '210507', '210509', '210512',
  '210825', '210827',
  '211025', '211029',
  -- group B: reference days
  '210915', '211013',
  '240918',
  '250917', '251112',
  '260415', '260715'
)
GROUP BY _TABLE_SUFFIX, hour
ORDER BY day, hour