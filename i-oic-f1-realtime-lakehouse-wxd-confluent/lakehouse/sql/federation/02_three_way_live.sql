-- Three sources in one statement:
--   kafka_live  the race that is finishing right now (Confluent topic, read in place)
--   fantasy_pg  who picked which driver (PostgreSQL app database)
--   Iceberg     each driver's career so far (Gold layer)
WITH live AS (
  SELECT json_extract_scalar(_message, '$.driver_id')                AS driver_id,
         CAST(json_extract_scalar(_message, '$.round') AS INTEGER)   AS round,
         CAST(json_extract_scalar(_message, '$.position') AS INTEGER) AS position,
         CAST(json_extract_scalar(_message, '$.points') AS DOUBLE)   AS points
  FROM kafka_live."default"."f1.race.results"
),
latest AS (SELECT * FROM live WHERE round = (SELECT max(round) FROM live)),
career AS (
  SELECT driver_id, sum(wins) AS career_wins, count(DISTINCT season) AS seasons
  FROM ${catalog}.${gold}.driver_season GROUP BY driver_id
)
SELECT l.position, d.driver_name, l.points AS race_points,
       count(p.manager_id) AS picked_by_managers,
       count_if(p.is_captain) AS captained_by,
       c.career_wins, c.seasons
FROM latest l
JOIN ${catalog}.${gold}.dim_driver d ON d.driver_id = l.driver_id
LEFT JOIN fantasy_pg.public.fantasy_picks p ON p.driver_id = l.driver_id AND p.season = 2026
LEFT JOIN career c ON c.driver_id = l.driver_id
GROUP BY 1, 2, 3, 6, 7
ORDER BY l.position
LIMIT 10
