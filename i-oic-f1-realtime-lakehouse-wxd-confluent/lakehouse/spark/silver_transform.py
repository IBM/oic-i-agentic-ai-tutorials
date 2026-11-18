"""SILVER: turn raw Bronze rows into clean, typed, de-duplicated Iceberg tables.

Runs on the watsonx.data Spark engine. What happens here, table by table:

- Types: strings become INT, DOUBLE and DATE; names get consistent casing.
- Structure: the nested driver name is flattened; race and sprint results become one
  `results` table with a `session_type` column.
- Data quality: rows that miss a business key go to `quarantine` with a reason, instead of
  silently disappearing. Blank circuit ids are repaired from the circuit's URL.
- Business meaning: 130+ free-text finish statuses become a `finish_category` and a
  `retirement_cause` (mechanical, incident, driver, other, or unknown when the source only
  says "Retired"), so "how reliable was this car?" has one correct answer.
- De-duplication on the real natural key. In the 1950s a driver could share several cars in
  one race, so a result is keyed by driver AND car number, not driver alone.
- Live data: if the Kafka stream has landed 2026 events in `f1_bronze.race_events`, they are
  parsed and merged in exactly like the files.

Every table is written with MERGE INTO and a row hash, so running the job again changes only
rows whose content changed. That makes it safe to re-run after every new race.

Arguments: --catalog <iceberg catalog> --warehouse <s3a://bucket>
"""

import argparse
import json

from pyspark.sql import DataFrame, SparkSession, Window, functions as F, types as T

FINISHED_STATUS = r"^(Finished|Lapped|\+\d+ Laps?)$"
INCIDENT_STATUS = r"(?i)^(accident|collision|collision damage|spun off|fatal accident|damage|debris|puncture|tyre puncture|broken wing|front wing|rear wing)$"
DRIVER_STATUS = r"(?i)^(physical|injury|injured|illness|driver unwell|eye injury|safety concerns|safety)$"
# From 2023 the source records most retirements only as "Retired", with no cause.
UNKNOWN_STATUS = r"(?i)^(retired|not classified)$"
OTHER_STATUS = r"(?i)^(withdrew|did not start|not restarted|excluded|disqualified|underweight)$"

EVENT_SCHEMA = T.StructType([
    T.StructField("season", T.IntegerType()), T.StructField("round", T.IntegerType()),
    T.StructField("session_type", T.StringType()), T.StructField("race_name", T.StringType()),
    T.StructField("race_date", T.StringType()), T.StructField("circuit_id", T.StringType()),
    T.StructField("driver_id", T.StringType()), T.StructField("constructor_id", T.StringType()),
    T.StructField("car_number", T.IntegerType()), T.StructField("grid", T.IntegerType()),
    T.StructField("position", T.IntegerType()), T.StructField("position_text", T.StringType()),
    T.StructField("points", T.DoubleType()), T.StructField("laps", T.IntegerType()),
    T.StructField("status", T.StringType()), T.StructField("event_time", T.StringType()),
])


def latest(df: DataFrame, keys: list[str], order_col: str = "_ingested_at") -> DataFrame:
    """Keep one row per key: the most recently ingested."""
    w = Window.partitionBy(*keys).orderBy(F.col(order_col).desc())
    return df.withColumn("_rn", F.row_number().over(w)).filter("_rn = 1").drop("_rn")


def merge(spark: SparkSession, df: DataFrame, target: str, keys: list[str], partition: str | None = None) -> dict:
    """Upsert df into target, touching only rows that are new or whose content changed.

    Each row carries a hash of its business columns. Rows whose key and hash already exist
    in the target are dropped before the MERGE: Iceberg rewrites every data file that holds a
    matched row, so merging unchanged rows would rewrite the whole table on every run.
    """
    business = [c for c in df.columns if not c.startswith("_")]
    df = df.withColumn("_row_hash", F.sha2(F.to_json(F.struct(*business)), 256))
    if not spark.catalog.tableExists(target):
        writer = df.limit(0).writeTo(target).using("iceberg").tableProperty("format-version", "2")
        if partition:
            writer = writer.partitionedBy(F.col(partition))
        writer.create()

    existing = spark.table(target).select(*[F.col(k).alias(f"_t_{k}") for k in keys], F.col("_row_hash").alias("_t_hash"))
    same = [df[k].eqNullSafe(existing[f"_t_{k}"]) for k in keys] + [df["_row_hash"] == existing["_t_hash"]]
    cond = same[0]
    for c in same[1:]:
        cond = cond & c
    changes = df.join(existing, cond, "left_anti").cache()
    n_changes = changes.count()
    if n_changes == 0:
        return {"rows": spark.table(target).count(), "inserted": 0, "updated": 0}

    before = spark.table(target).count()
    changes.createOrReplaceTempView("_changes")
    on = " AND ".join(f"t.{k} <=> s.{k}" for k in keys)
    spark.sql(f"""
        MERGE INTO {target} t USING _changes s ON {on}
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)
    after = spark.table(target).count()
    return {"rows": after, "inserted": after - before, "updated": n_changes - (after - before)}


def to_int(c: str):
    return F.col(c).cast("int")


def build_circuits(b) -> DataFrame:
    raw = b("circuits")
    # Two rows arrive with a blank circuitId. Repair them from another row with the same URL.
    by_url = (raw.filter("circuitId IS NOT NULL AND circuitId <> ''")
              .groupBy("url").agg(F.first("circuitId").alias("_id_from_url")))
    fixed = (raw.join(by_url, "url", "left")
             .withColumn("circuit_id", F.coalesce(F.when(F.col("circuitId") != "", F.col("circuitId")), F.col("_id_from_url"))))
    return latest(fixed.filter("circuit_id IS NOT NULL").select(
        "circuit_id",
        F.initcap("circuitName").alias("circuit_name"),
        F.initcap("locality").alias("locality"),
        F.col("country"),
        F.col("lat").cast("double").alias("latitude"),
        F.col("long").cast("double").alias("longitude"),
        "_ingested_at"), ["circuit_id"])


def build_constructors(b) -> DataFrame:
    return latest(b("constructors").select(
        F.col("constructorId").alias("constructor_id"),
        F.col("name").alias("constructor_name"),
        F.initcap("nationality").alias("nationality"),
        "_ingested_at"), ["constructor_id"])


def build_drivers(b) -> DataFrame:
    first, last = F.initcap("name.givenName"), F.initcap("name.familyName")
    return latest(b("drivers").select(
        F.col("driverId").alias("driver_id"),
        first.alias("first_name"), last.alias("last_name"),
        F.concat_ws(" ", first, last).alias("driver_name"),
        F.to_date("dateOfBirth").alias("date_of_birth"),
        F.initcap("nationality").alias("nationality"),
        "_ingested_at"), ["driver_id"])


def parse_events(spark: SparkSession, bronze_ns: str) -> DataFrame | None:
    """2026 results that the Kafka stream landed in Bronze as raw JSON messages."""
    if not spark.catalog.tableExists(f"{bronze_ns}.race_events"):
        return None
    ev = spark.table(f"{bronze_ns}.race_events")
    return ev.withColumn("e", F.from_json(F.col("value"), EVENT_SCHEMA)).select("e.*", "_ingested_at",
                                                                                 F.col("value").alias("_raw"))


def build_races(b, events: DataFrame | None) -> DataFrame:
    races = b("races").select(
        to_int("season").alias("season"), to_int("round").alias("round"),
        F.initcap("raceName").alias("race_name"), F.to_date("date").alias("race_date"),
        F.col("circuitId").alias("circuit_id"), "_ingested_at")
    if events is not None:
        races = races.unionByName(events.select(
            "season", "round", F.initcap("race_name").alias("race_name"),
            F.to_date("race_date").alias("race_date"), "circuit_id", "_ingested_at"))
    return latest(races.filter("season IS NOT NULL AND round IS NOT NULL"), ["season", "round"])


def build_results(b, events: DataFrame | None) -> tuple[DataFrame, DataFrame]:
    def from_files(table: str, session: str) -> DataFrame:
        return b(table).select(
            F.lit(session).alias("session_type"),
            to_int("season").alias("season"), to_int("round").alias("round"),
            F.col("driverId").alias("driver_id"), F.col("constructorId").alias("constructor_id"),
            to_int("number").alias("car_number"), to_int("grid").alias("grid"),
            to_int("position").alias("position"), F.col("positionText").alias("position_text"),
            F.col("points").cast("double").alias("points"), to_int("laps").alias("laps"),
            F.col("status"), "_ingested_at", F.to_json(F.struct("*")).alias("_raw"))

    rows = from_files("results", "RACE").unionByName(from_files("sprints", "SPRINT"))
    if events is not None:
        rows = rows.unionByName(events.select(
            "session_type", "season", "round", "driver_id", "constructor_id", "car_number", "grid",
            "position", "position_text", "points", "laps", "status", "_ingested_at", "_raw"))

    missing = (F.when(F.col("season").isNull(), "missing season")
                .when(F.col("round").isNull(), "missing round")
                .when(F.col("driver_id").isNull(), "missing driver_id")
                .when(F.col("constructor_id").isNull(), "missing constructor_id"))
    rows = rows.withColumn("_reject_reason", missing)
    rejects = rows.filter("_reject_reason IS NOT NULL").select(
        F.lit("results").alias("source_table"), F.col("_reject_reason").alias("reason"),
        F.col("_raw").alias("raw_record"), "_ingested_at")

    classified = F.col("position_text").rlike(r"^\d+$")
    finish = (F.when(F.col("position_text") == "D", "disqualified")
               .when(F.col("position_text").isin("W", "N"), "did_not_start")
               .when(F.col("status").rlike(FINISHED_STATUS), "finished")
               .otherwise("retired"))
    cause = (F.when(F.col("finish_category") != "retired", None)
              .when(F.col("status").rlike(INCIDENT_STATUS), "incident")
              .when(F.col("status").rlike(DRIVER_STATUS), "driver")
              .when(F.col("status").rlike(UNKNOWN_STATUS), "unknown")
              .when(F.col("status").rlike(OTHER_STATUS), "other")
              .otherwise("mechanical"))
    good = (rows.filter("_reject_reason IS NULL")
            .withColumn("is_classified", classified)
            .withColumn("finish_category", finish)
            .withColumn("retirement_cause", cause)
            .withColumn("is_win", F.col("position_text") == "1")
            .withColumn("is_podium", F.col("position_text").isin("1", "2", "3"))
            .drop("_reject_reason", "_raw"))
    good = latest(good, ["session_type", "season", "round", "driver_id", "car_number"])
    return good.select(
        "session_type", "season", "round", "driver_id", "constructor_id", "car_number", "grid",
        "position", "position_text", "is_classified", "points", "laps", "status", "finish_category",
        "retirement_cause", "is_win", "is_podium", "_ingested_at"), rejects


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--warehouse", required=True)
    ap.add_argument("--bronze", default="f1_bronze")
    ap.add_argument("--silver", default="f1_silver")
    a = ap.parse_args()

    spark = SparkSession.builder.appName("f1-silver-transform").getOrCreate()
    bronze_ns, silver_ns = f"{a.catalog}.{a.bronze}", f"{a.catalog}.{a.silver}"
    spark.sql(f"CREATE DATABASE IF NOT EXISTS {silver_ns} LOCATION '{a.warehouse}/{a.silver}'")

    def b(t: str) -> DataFrame:
        return spark.table(f"{bronze_ns}.{t}")

    events = parse_events(spark, bronze_ns)
    results, rejects = build_results(b, events)

    summary = {
        "circuits": merge(spark, build_circuits(b), f"{silver_ns}.circuits", ["circuit_id"]),
        "constructors": merge(spark, build_constructors(b), f"{silver_ns}.constructors", ["constructor_id"]),
        "drivers": merge(spark, build_drivers(b), f"{silver_ns}.drivers", ["driver_id"]),
        "races": merge(spark, build_races(b, events), f"{silver_ns}.races", ["season", "round"]),
        "results": merge(spark, results, f"{silver_ns}.results",
                         ["session_type", "season", "round", "driver_id", "car_number"], partition="season"),
    }
    # Quarantine reflects the current Bronze contents, so it is replaced on every run.
    rejects.writeTo(f"{silver_ns}.quarantine").using("iceberg").createOrReplace()
    summary["quarantine"] = {"rows": spark.table(f"{silver_ns}.quarantine").count()}

    for t, m in summary.items():
        print(f"silver.{t}: {m}")
    print("SILVER_SUMMARY " + json.dumps(summary))
    spark.stop()


if __name__ == "__main__":
    main()
