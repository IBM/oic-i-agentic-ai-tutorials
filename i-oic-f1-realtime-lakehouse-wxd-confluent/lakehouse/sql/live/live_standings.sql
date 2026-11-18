-- 2026 standings right now: Gold-layer points plus races that are still only on Kafka.
WITH live AS (
  SELECT json_extract_scalar(_message, '$.driver_id')                AS driver_id,
         CAST(json_extract_scalar(_message, '$.round') AS INTEGER)   AS round,
         CAST(json_extract_scalar(_message, '$.points') AS DOUBLE)   AS points
  FROM kafka_live."default"."f1.race.results"
),
pending AS (
  SELECT driver_id, sum(points) AS live_points
  FROM live
  WHERE round NOT IN (SELECT DISTINCT round FROM ${catalog}.${gold}.fact_session_result WHERE season = 2026)
  GROUP BY driver_id
),
lake AS (
  SELECT driver_id, points AS lakehouse_points
  FROM ${catalog}.${gold}.driver_season
  WHERE season = 2026
)
SELECT d.driver_name,
       coalesce(l.lakehouse_points, 0)                                AS lakehouse_points,
       coalesce(p.live_points, 0)                                     AS live_points,
       coalesce(l.lakehouse_points, 0) + coalesce(p.live_points, 0)   AS total_points
FROM ${catalog}.${gold}.dim_driver d
LEFT JOIN lake l    ON l.driver_id = d.driver_id
LEFT JOIN pending p ON p.driver_id = d.driver_id
WHERE l.driver_id IS NOT NULL OR p.driver_id IS NOT NULL
ORDER BY total_points DESC
LIMIT 10
