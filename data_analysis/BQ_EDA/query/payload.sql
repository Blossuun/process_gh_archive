SELECT
  type,
  COUNT(*) AS events,
  COUNTIF(JSON_VALUE(payload, '$.action') IS NOT NULL) AS has_action,
  COUNTIF(JSON_VALUE(payload, '$.ref_type') IS NOT NULL) AS has_ref_type
FROM `githubarchive.day.20260824`
GROUP BY type
ORDER BY events DESC