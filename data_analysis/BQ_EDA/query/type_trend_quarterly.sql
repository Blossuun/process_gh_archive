-- Event type volume, one sample day per quarter from 2016 Q3 to 2026 Q3.
--
-- Purpose: find when WatchEvent collapsed. WatchEvent is the only star proxy
-- in GH Archive, and goal 2's spike ratio is built on it. The analysis window
-- must end before the collapse.
--
-- Scans the `type` column only, never `payload`, so the cost stays low.
-- A full daily scan of the same range would be roughly 112 GB; quarterly
-- sampling narrows the collapse to a quarter first, and only that quarter
-- then needs a denser look.
--
-- Sample selection, from analysis/daily_volume.csv:
--   - the Wednesday nearest each quarter's midpoint, so day-of-week effects
--     do not confound comparisons between quarters
--   - never a day flagged as a partial load (is_anomaly = 1), so a sample is
--     not mistaken for a collapse
--
-- Read both `events` and `share_pct`. A falling share can mean the type
-- shrank or that another type grew; the absolute count settles which.
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
  '160817', '161116', '170215', '170517',
  '170816', '171115', '180214', '180516',
  '180815', '181114', '190213', '190515',
  '190814', '191113', '200212', '200513',
  '200812', '201118', '210217', '210512',
  '210818', '211117', '220216', '220518',
  '220817', '221116', '230215', '230517',
  '230816', '231115', '240214', '240515',
  '240814', '241113', '250212', '250514',
  '250813', '251112', '260218', '260513',
  '260812'
)
GROUP BY _TABLE_SUFFIX, type
ORDER BY day, events DESC