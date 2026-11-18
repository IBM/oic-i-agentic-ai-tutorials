"""Settings for the F1 lakehouse, read from the project's .env file."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _req(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing {name} in .env (see .env.example)")
    return value


@dataclass(frozen=True)
class Settings:
    # watsonx.data
    wxd_host: str
    wxd_crn: str
    api_key: str
    wxd_user: str
    presto_engine: str
    presto_host: str
    spark_engine: str
    catalog: str
    bucket: str
    cos_endpoint: str
    landing_bucket: str
    landing_access_key: str
    landing_secret_key: str
    # Confluent
    kafka_bootstrap: str
    kafka_key: str
    kafka_secret: str
    kafka_topic: str

    # Medallion schemas
    bronze: str = "f1_bronze"
    silver: str = "f1_silver"
    gold: str = "f1_gold"

    # Object-storage layout
    landing_prefix: str = "f1"
    apps_prefix: str = "spark-apps"
    checkpoint_prefix: str = "checkpoints"

    @property
    def warehouse(self) -> str:
        return f"s3a://{self.bucket}"

    @property
    def landing_uri(self) -> str:
        return f"s3a://{self.landing_bucket}/{self.landing_prefix}"

    @property
    def cos_direct_endpoint(self) -> str:
        """Spark runs inside IBM Cloud, so it reaches object storage on the direct endpoint."""
        return self.cos_endpoint.replace("://s3.", "://s3.direct.")


def load() -> Settings:
    return Settings(
        wxd_host=_req("WXD_HOST").rstrip("/"),
        wxd_crn=_req("WXD_CRN"),
        api_key=_req("WXD_API_KEY"),
        wxd_user=_req("WXD_USER"),
        presto_engine=_req("PRESTO_ENGINE_ID"),
        presto_host=_req("PRESTO_HOST"),
        spark_engine=_req("SPARK_ENGINE_ID"),
        catalog=_req("ICEBERG_CATALOG"),
        bucket=_req("COS_BUCKET"),
        cos_endpoint=_req("COS_ENDPOINT").rstrip("/"),
        landing_bucket=os.getenv("LANDING_BUCKET", "").strip(),
        landing_access_key=os.getenv("LANDING_HMAC_ACCESS_KEY_ID", "").strip(),
        landing_secret_key=os.getenv("LANDING_HMAC_SECRET_ACCESS_KEY", "").strip(),
        kafka_bootstrap=os.getenv("KAFKA_BOOTSTRAP", ""),
        kafka_key=os.getenv("KAFKA_API_KEY", ""),
        kafka_secret=os.getenv("KAFKA_API_SECRET", ""),
        kafka_topic=os.getenv("KAFKA_TOPIC", "f1.race.results"),
        # Optional overrides, for example to build a second copy of the lakehouse for testing.
        bronze=os.getenv("BRONZE_SCHEMA", "f1_bronze"),
        silver=os.getenv("SILVER_SCHEMA", "f1_silver"),
        gold=os.getenv("GOLD_SCHEMA", "f1_gold"),
        checkpoint_prefix=os.getenv("CHECKPOINT_PREFIX", "checkpoints"),
    )
