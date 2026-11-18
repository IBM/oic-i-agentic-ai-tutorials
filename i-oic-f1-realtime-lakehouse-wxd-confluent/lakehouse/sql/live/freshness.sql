-- Where is each 2026 race right now: only on the Kafka topic, or already in the lakehouse?
WITH kafka AS (
  SELECT CAST(json_extract_scalar(_message, '$.round') AS INTEGER) AS round,
         max(json_extract_scalar(_message, '$.race_name'))         AS race,
         count(*)                                                   AS results_on_topic
  FROM kafka_live."default"."f1.race.results"
  GROUP BY 1
),
lake AS (
  SELECT round, count(*) AS results_in_gold
  FROM ${catalog}.${gold}.fact_session_result
  WHERE season = 2026
  GROUP BY 1
)
SELECT k.round, k.race, k.results_on_topic,
       coalesce(l.results_in_gold, 0) AS results_in_gold,
       CASE WHEN l.round IS NULL THEN 'only on Kafka' ELSE 'in the lakehouse' END AS status
FROM kafka k
LEFT JOIN lake l ON l.round = k.round
ORDER BY k.round
