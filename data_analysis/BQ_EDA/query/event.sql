SELECT type, COUNT(*) AS events
FROM `githubarchive.day.20260824`
GROUP BY type
ORDER BY events DESC