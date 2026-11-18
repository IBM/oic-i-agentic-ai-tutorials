-- One row per driver, car and session (Grand Prix or sprint). Partitioned by season,
-- because almost every question filters on a season or a range of seasons.

DROP TABLE IF EXISTS ${catalog}.${gold}.fact_session_result;
CREATE TABLE ${catalog}.${gold}.fact_session_result
WITH (partitioning = ARRAY['season']) AS
SELECT r.session_type,
       r.round,
       r.driver_id,
       r.constructor_id,
       ra.circuit_id,
       ra.race_date,
       r.car_number,
       r.grid,
       r.position,
       r.position_text,
       r.is_classified,
       r.points,
       r.laps,
       r.status,
       r.finish_category,
       r.retirement_cause,
       r.is_win,
       r.is_podium,
       r.grid = 1 AS started_on_pole,
       r.season
FROM ${catalog}.${silver}.results r
LEFT JOIN ${catalog}.${silver}.races ra ON ra.season = r.season AND ra.round = r.round;
