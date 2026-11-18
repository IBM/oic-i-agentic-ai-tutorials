-- Conformed dimensions -------------------------------------------------------

DROP TABLE IF EXISTS ${catalog}.${gold}.dim_driver;
CREATE TABLE ${catalog}.${gold}.dim_driver AS
SELECT d.driver_id,
       d.driver_name,
       d.first_name,
       d.last_name,
       d.nationality,
       d.date_of_birth,
       min(r.season) AS first_season,
       max(r.season) AS last_season
FROM ${catalog}.${silver}.drivers d
LEFT JOIN ${catalog}.${silver}.results r ON r.driver_id = d.driver_id
GROUP BY 1, 2, 3, 4, 5, 6;

DROP TABLE IF EXISTS ${catalog}.${gold}.dim_constructor;
CREATE TABLE ${catalog}.${gold}.dim_constructor AS
SELECT constructor_id, constructor_name, nationality
FROM ${catalog}.${silver}.constructors;

DROP TABLE IF EXISTS ${catalog}.${gold}.dim_circuit;
CREATE TABLE ${catalog}.${gold}.dim_circuit AS
SELECT circuit_id, circuit_name, locality, country, latitude, longitude
FROM ${catalog}.${silver}.circuits;

DROP TABLE IF EXISTS ${catalog}.${gold}.dim_race;
CREATE TABLE ${catalog}.${gold}.dim_race AS
SELECT ra.season,
       ra.round,
       ra.race_name,
       ra.race_date,
       ra.circuit_id,
       c.circuit_name,
       c.country,
       EXISTS (SELECT 1 FROM ${catalog}.${silver}.results s
               WHERE s.season = ra.season AND s.round = ra.round AND s.session_type = 'SPRINT') AS has_sprint
FROM ${catalog}.${silver}.races ra
LEFT JOIN ${catalog}.${silver}.circuits c ON c.circuit_id = ra.circuit_id;
