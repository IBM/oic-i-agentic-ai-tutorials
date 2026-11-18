-- How many 2026 results did the lakehouse hold before and after the stream landed?
-- Replace <SNAPSHOT_ID> with a snapshot_id from 01_snapshots.sql.
SELECT 'now' AS version, count(*) AS results_2026
FROM ${catalog}.${silver}.results WHERE season = 2026
UNION ALL
SELECT 'before stream', count(*)
FROM ${catalog}.${silver}.results FOR VERSION AS OF <SNAPSHOT_ID>
WHERE season = 2026
