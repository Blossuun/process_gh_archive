SELECT
  _TABLE_SUFFIX AS day,
  COUNT(*) AS total_events,
  COUNTIF(type = 'PushEvent') AS push_events,
  COUNTIF(type = 'WatchEvent') AS watch_events,
  COUNTIF(type = 'PullRequestEvent') AS pr_events,
  ROUND(COUNTIF(type = 'PushEvent') / COUNT(*) * 100, 1) AS push_pct,
  ROUND(COUNTIF(type = 'WatchEvent') / COUNT(*) * 100, 1) AS watch_pct
FROM `githubarchive.day.2026*`
WHERE _TABLE_SUFFIX BETWEEN '0727' AND '0825'
GROUP BY day
ORDER BY day