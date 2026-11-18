-- Every write to an Iceberg table creates a snapshot. List them for Silver results:
SELECT committed_at, snapshot_id, operation,
       element_at(summary, 'added-records')   AS added,
       element_at(summary, 'deleted-records') AS deleted
FROM ${catalog}.${silver}."results$snapshots"
ORDER BY committed_at
