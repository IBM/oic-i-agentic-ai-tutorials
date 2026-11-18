-- GOLD: business-ready star schema, built with Presto SQL from the Silver tables.
-- Each run rebuilds the Gold tables from Silver, so Gold is always reproducible.
CREATE SCHEMA IF NOT EXISTS ${catalog}.${gold} WITH (location = '${warehouse}/${gold}');
