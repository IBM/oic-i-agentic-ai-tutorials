-- Season marts: the tables most questions are answered from.
-- points include sprint points; wins, podiums and poles count Grand Prix races only.
-- points_rank is the order by points (then wins) in that season. Before 1991 only a
-- driver's best results counted towards the title, so points_rank = 1 is not always the
-- official champion (for example 1988).

DROP TABLE IF EXISTS ${catalog}.${gold}.driver_season;
CREATE TABLE ${catalog}.${gold}.driver_season AS
WITH s AS (
  SELECT f.season,
         f.driver_id,
         array_join(array_sort(array_agg(DISTINCT c.constructor_name)), ', ') AS constructors,
         count(DISTINCT CASE WHEN f.session_type = 'RACE' THEN f.round END) AS races,
         sum(f.points) AS points,
         count_if(f.session_type = 'RACE' AND f.is_win) AS wins,
         count_if(f.session_type = 'RACE' AND f.is_podium) AS podiums,
         count_if(f.session_type = 'RACE' AND f.started_on_pole) AS pole_starts,
         count_if(f.session_type = 'SPRINT' AND f.is_win) AS sprint_wins,
         count_if(f.session_type = 'RACE' AND f.finish_category = 'retired') AS retirements,
         round(avg(CASE WHEN f.session_type = 'RACE' AND f.is_classified THEN f.position END), 2) AS avg_finish
  FROM ${catalog}.${gold}.fact_session_result f
  LEFT JOIN ${catalog}.${gold}.dim_constructor c ON c.constructor_id = f.constructor_id
  GROUP BY 1, 2
)
SELECT s.season, s.driver_id, d.driver_name, d.nationality, s.constructors, s.races, s.points,
       s.wins, s.podiums, s.pole_starts, s.sprint_wins, s.retirements, s.avg_finish,
       rank() OVER (PARTITION BY s.season ORDER BY s.points DESC, s.wins DESC) AS points_rank
FROM s
LEFT JOIN ${catalog}.${gold}.dim_driver d ON d.driver_id = s.driver_id;

DROP TABLE IF EXISTS ${catalog}.${gold}.constructor_season;
CREATE TABLE ${catalog}.${gold}.constructor_season AS
WITH s AS (
  SELECT season,
         constructor_id,
         count_if(session_type = 'RACE') AS car_starts,
         sum(points) AS points,
         count_if(session_type = 'RACE' AND is_win) AS wins,
         count_if(session_type = 'RACE' AND is_podium) AS podiums,
         count_if(session_type = 'RACE' AND finish_category = 'retired') AS retirements,
         count_if(session_type = 'RACE' AND retirement_cause = 'mechanical') AS mechanical_retirements,
         count_if(session_type = 'RACE' AND retirement_cause = 'incident') AS incident_retirements,
         count_if(session_type = 'RACE' AND retirement_cause = 'unknown') AS unknown_cause_retirements,
         count_if(session_type = 'RACE' AND finish_category = 'finished') AS finishes
  FROM ${catalog}.${gold}.fact_session_result
  GROUP BY 1, 2
)
SELECT s.season, s.constructor_id, c.constructor_name, s.car_starts, s.points, s.wins, s.podiums,
       s.retirements, s.mechanical_retirements, s.incident_retirements, s.unknown_cause_retirements,
       round(100.0 * s.finishes / nullif(s.car_starts, 0), 1) AS finish_rate_pct,
       -- Share of starts without a mechanical retirement. Left NULL when more than a fifth
       -- of the retirements have no recorded cause (most of 2023 onwards).
       CASE WHEN s.unknown_cause_retirements * 5 <= s.retirements
            THEN round(100.0 * (s.car_starts - s.mechanical_retirements) / nullif(s.car_starts, 0), 1)
       END AS reliability_pct,
       rank() OVER (PARTITION BY s.season ORDER BY s.points DESC, s.wins DESC) AS points_rank
FROM s
LEFT JOIN ${catalog}.${gold}.dim_constructor c ON c.constructor_id = s.constructor_id;
