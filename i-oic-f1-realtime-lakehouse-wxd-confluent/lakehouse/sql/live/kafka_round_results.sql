-- Read 2026 race results straight off the Confluent topic: no pipeline, no copy.
SELECT json_extract_scalar(_message, '$.race_name')                  AS race,
       CAST(json_extract_scalar(_message, '$.position') AS INTEGER)   AS pos,
       json_extract_scalar(_message, '$.driver_id')                   AS driver_id,
       json_extract_scalar(_message, '$.constructor_id')              AS team,
       CAST(json_extract_scalar(_message, '$.points') AS DOUBLE)      AS points,
       json_extract_scalar(_message, '$.status')                      AS status,
       _partition_offset                                              AS kafka_offset
FROM kafka_live."default"."f1.race.results"
ORDER BY kafka_offset
LIMIT 25
