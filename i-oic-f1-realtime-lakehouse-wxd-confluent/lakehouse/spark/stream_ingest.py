"""BRONZE (streaming): land new Kafka messages from Confluent Cloud in an Iceberg table.

Runs on the watsonx.data Spark engine with Spark Structured Streaming.

- trigger(availableNow=True) reads every message published since the last run, writes it,
  and stops. You get streaming semantics (exactly-once, offsets tracked in a checkpoint)
  without paying for an engine that waits for a race that happens every two weeks.
- The checkpoint lives in object storage, so each run continues where the last one stopped.
- Bronze keeps the message exactly as it arrived: the raw JSON value plus Kafka metadata.
  Parsing happens in Silver.

Kafka credentials arrive as environment variables (KAFKA_BOOTSTRAP, KAFKA_API_KEY,
KAFKA_API_SECRET), never as arguments.

Arguments: --catalog <iceberg catalog> --warehouse <s3a://bucket> --topic <topic>
           --checkpoint <s3a://bucket/checkpoints/...>
"""

import argparse
import os

from pyspark.sql import SparkSession, functions as F


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--warehouse", required=True)
    ap.add_argument("--topic", required=True)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--schema", default="f1_bronze")
    a = ap.parse_args()

    spark = SparkSession.builder.appName("f1-stream-ingest").getOrCreate()
    target = f"{a.catalog}.{a.schema}.race_events"
    spark.sql(f"CREATE DATABASE IF NOT EXISTS {a.catalog}.{a.schema} LOCATION '{a.warehouse}/{a.schema}'")
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {target} (
            key STRING, value STRING, topic STRING, kafka_partition INT, kafka_offset BIGINT,
            kafka_timestamp TIMESTAMP, _ingested_at TIMESTAMP, _batch_id BIGINT
        ) USING iceberg TBLPROPERTIES ('format-version' = '2')
    """)
    landed = []  # rows written per micro-batch (foreachBatch runs on the driver)

    jaas = ('org.apache.kafka.common.security.plain.PlainLoginModule required '
            f'username="{os.environ["KAFKA_API_KEY"]}" password="{os.environ["KAFKA_API_SECRET"]}";')
    stream = (spark.readStream.format("kafka")
              .option("kafka.bootstrap.servers", os.environ["KAFKA_BOOTSTRAP"])
              .option("kafka.security.protocol", "SASL_SSL")
              .option("kafka.sasl.mechanism", "PLAIN")
              .option("kafka.sasl.jaas.config", jaas)
              .option("subscribe", a.topic)
              .option("startingOffsets", "earliest")
              .option("failOnDataLoss", "false")
              .load())

    def write_batch(df, batch_id):
        landed.append(df.count())
        (df.select(F.col("key").cast("string"), F.col("value").cast("string"), "topic",
                   F.col("partition").alias("kafka_partition"), F.col("offset").alias("kafka_offset"),
                   F.col("timestamp").alias("kafka_timestamp"),
                   F.current_timestamp().alias("_ingested_at"), F.lit(batch_id).cast("bigint").alias("_batch_id"))
           .writeTo(target).append())

    q = (stream.writeStream.foreachBatch(write_batch)
         .option("checkpointLocation", a.checkpoint)
         .trigger(availableNow=True)
         .start())
    q.awaitTermination()

    spark.sql(f"REFRESH TABLE {target}")
    total = spark.table(target).count()
    print(f"STREAM_SUMMARY new_messages={sum(landed)} micro_batches={len(landed)} total={total}")
    spark.stop()


if __name__ == "__main__":
    main()
