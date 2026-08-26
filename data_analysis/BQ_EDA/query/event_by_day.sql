SELECT
  _TABLE_SUFFIX AS day,
  type,
  COUNT(*) AS events
FROM `githubarchive.day.2026*`
WHERE _TABLE_SUFFIX BETWEEN '0727' AND '0825'
GROUP BY day, type
ORDER BY day, events DESC