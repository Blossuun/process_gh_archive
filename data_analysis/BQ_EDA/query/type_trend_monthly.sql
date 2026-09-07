-- Event type volume, two sample days per month from 2024-09 to 2025-12.
--
-- Purpose: pin down, to the month, when WatchEvent stopped being a usable
-- star proxy. query/type_trend_quarterly.sql narrowed it to somewhere between
-- 2025-05 and 2025-08; this fills in the months between, with a run-up from
-- 2024-09 for a healthy baseline and a run-out to 2025-12 to confirm the
-- decline continues.
--
-- Scans the `type` column only, never `payload`. Measured cost is roughly
-- 37 MB per day at current volumes, so 32 days is about 1.2 GB.
--
-- Sample selection, from analysis/daily_volume.csv:
--   - two Wednesdays per month (the 2nd and 4th), so that a single odd day
--     cannot be mistaken for the boundary
--   - never a day flagged as a partial load (is_anomaly = 1)
--
-- Read `events`, not `share_pct`. Share moves when any type moves; only the
-- absolute count says whether WatchEvent itself is disappearing.
--
-- The `day.20*` prefix excludes the `yesterday` view, which cannot be read
-- through a wildcard. _TABLE_SUFFIX is therefore the table id minus '20'.
SELECT
  CONCAT('20', _TABLE_SUFFIX) AS day,
  type,
  COUNT(*) AS events,
  ROUND(
    COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY _TABLE_SUFFIX) * 100,
    3
  ) AS share_pct
FROM `githubarchive.day.20*`
WHERE _TABLE_SUFFIX IN (
  '240911', '240925', '241009', '241023',
  '241113', '241127', '241211', '241225',
  '250108', '250122', '250212', '250226',
  '250312', '250326', '250409', '250423',
  '250514', '250528', '250611', '250625',
  '250709', '250723', '250813', '250827',
  '250910', '250924', '251008', '251022',
  '251112', '251126', '251210', '251224'
)
GROUP BY _TABLE_SUFFIX, type
ORDER BY day, events DESC