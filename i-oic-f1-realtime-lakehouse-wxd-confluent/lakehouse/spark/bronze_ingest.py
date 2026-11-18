"""BRONZE: land the raw F1 files in Apache Iceberg tables, exactly as they arrived.

Runs on the watsonx.data Spark engine. Bronze is the system of record for raw data, so
nothing is cleaned here:

- CSV columns stay strings and JSON is read with primitivesAsString, so a bad value in one
  file can never fail the load or be silently coerced.
- Nested JSON (a driver's name) stays nested.
- Every row gets lineage columns: the file it came from, when it was loaded, and a batch id.

Arguments: --catalog <iceberg catalog> --landing <s3a://bucket/landing/f1> --warehouse <s3a://bucket>
"""

import argparse
import json

from pyspark.sql import SparkSession, functions as F

# table name -> (format, path under landing/, reader options)
SOURCES = {
    "circuits":     ("csv",  "circuits.csv",      {"header": "true"}),
    "races":        ("csv",  "races.csv",         {"header": "true"}),
    "constructors": ("json", "constructors.json", {"primitivesAsString": "true"}),
    "drivers":      ("json", "drivers.json",      {"primitivesAsString": "true"}),
    "results":      ("json", "results/*.json",    {"primitivesAsString": "true"}),
    "sprints":      ("json", "sprints/*.json",    {"primitivesAsString": "true", "multiLine": "true"}),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--landing", required=True)
    ap.add_argument("--warehouse", required=True)
    ap.add_argument("--schema", default="f1_bronze")
    a = ap.parse_args()

    spark = SparkSession.builder.appName("f1-bronze-ingest").getOrCreate()
    ns = f"{a.catalog}.{a.schema}"
    spark.sql(f"CREATE DATABASE IF NOT EXISTS {ns} LOCATION '{a.warehouse}/{a.schema}'")

    batch_id = spark.sql("SELECT date_format(current_timestamp(), 'yyyyMMddHHmmss')").first()[0]
    summary = {}
    for table, (fmt, path, opts) in SOURCES.items():
        df = (spark.read.format(fmt).options(**opts).load(f"{a.landing}/{path}")
              .withColumn("_source_file", F.element_at(F.split(F.input_file_name(), "/"), -1))
              .withColumn("_ingested_at", F.current_timestamp())
              .withColumn("_batch_id", F.lit(batch_id)))
        (df.writeTo(f"{ns}.{table}").using("iceberg")
           .tableProperty("format-version", "2")
           .createOrReplace())
        summary[table] = spark.table(f"{ns}.{table}").count()
        print(f"bronze.{table}: {summary[table]} rows")

    print("BRONZE_SUMMARY " + json.dumps(summary))
    spark.stop()


if __name__ == "__main__":
    main()
