-- Fantasy-league standings: picks live in PostgreSQL (Neon), points live in the Iceberg
-- lakehouse. Presto joins them at query time; nothing is copied between systems.
SELECT m.team_name,
       m.manager_name,
       array_join(array_agg(CASE WHEN p.is_captain THEN d.driver_name || ' (C)' ELSE d.driver_name END), ', ') AS drivers,
       sum(CASE WHEN p.is_captain THEN 2 * d.points ELSE d.points END) AS fantasy_points
FROM fantasy_pg.public.fantasy_picks p
JOIN fantasy_pg.public.fantasy_managers m ON m.manager_id = p.manager_id
JOIN ${catalog}.${gold}.driver_season d ON d.driver_id = p.driver_id AND d.season = p.season
WHERE p.season = 2026
GROUP BY 1, 2
ORDER BY fantasy_points DESC
LIMIT 10
