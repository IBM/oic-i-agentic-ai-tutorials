"""
create_topic.py
Creates a Kafka topic via the Confluent Cloud Kafka REST API (v3).
Idempotent: if the topic already exists, validates it instead of failing.
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration — loaded exclusively from .env
# ---------------------------------------------------------------------------
REQUIRED_VARS = [
    "CONFLUENT_CLOUD_API_KEY",
    "CONFLUENT_CLOUD_API_SECRET",
    "CONFLUENT_ENVIRONMENT_ID",
    "CONFLUENT_CLUSTER_ID",
    "CONFLUENT_CLUSTER_REST_ENDPOINT",
    "TOPIC_NAME",
    "TOPIC_PARTITIONS",
    "TOPIC_RETENTION_MS",
]

missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
if missing:
    print(f"[ERROR] Missing required environment variables: {', '.join(missing)}")
    sys.exit(1)

API_KEY      = os.environ["CONFLUENT_CLOUD_API_KEY"]
API_SECRET   = os.environ["CONFLUENT_CLOUD_API_SECRET"]
CLUSTER_ID   = os.environ["CONFLUENT_CLUSTER_ID"]
REST_ENDPOINT = os.environ["CONFLUENT_CLUSTER_REST_ENDPOINT"].rstrip("/")
TOPIC_NAME   = os.environ["TOPIC_NAME"]
TOPIC_PARTITIONS = int(os.environ["TOPIC_PARTITIONS"])
TOPIC_RETENTION_MS = os.environ["TOPIC_RETENTION_MS"]

AUTH = (API_KEY, API_SECRET)
HEADERS = {"Content-Type": "application/json"}

BASE_URL   = f"{REST_ENDPOINT}/kafka/v3/clusters/{CLUSTER_ID}"
TOPICS_URL = f"{BASE_URL}/topics"
TOPIC_URL  = f"{TOPICS_URL}/{TOPIC_NAME}"
CONFIG_URL = f"{TOPIC_URL}/configs/retention.ms"

print(f"[INFO] API key   : {API_KEY}")
print(f"[INFO] Cluster   : {CLUSTER_ID}")
print(f"[INFO] Endpoint  : {REST_ENDPOINT}")
print(f"[INFO] Topic     : {TOPIC_NAME}")
print(f"[INFO] Partitions: {TOPIC_PARTITIONS}")
print(f"[INFO] Retention : {TOPIC_RETENTION_MS} ms")
print()

# ---------------------------------------------------------------------------
# Step 1 — Create topic (idempotent: 409 = already exists)
# ---------------------------------------------------------------------------
payload = {
    "topic_name": TOPIC_NAME,
    "partitions_count": TOPIC_PARTITIONS,
    "configs": [
        {"name": "retention.ms", "value": TOPIC_RETENTION_MS}
    ],
}

resp = requests.post(TOPICS_URL, auth=AUTH, headers=HEADERS, json=payload)

if resp.status_code == 201:
    print(f"[OK] Topic '{TOPIC_NAME}' created successfully.")
elif resp.status_code == 409:
    print(f"[INFO] Topic '{TOPIC_NAME}' already exists — validating configuration.")
else:
    print(f"[ERROR] Failed to create topic. HTTP {resp.status_code}: {resp.text}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Step 2 — GET topic to confirm it exists
# ---------------------------------------------------------------------------
resp = requests.get(TOPIC_URL, auth=AUTH, headers=HEADERS)
if resp.status_code != 200:
    print(f"[ERROR] Could not retrieve topic. HTTP {resp.status_code}: {resp.text}")
    sys.exit(1)

topic_data = resp.json()
actual_partitions = topic_data.get("partitions_count", "unknown")

# ---------------------------------------------------------------------------
# Step 3 — GET retention.ms config
# ---------------------------------------------------------------------------
resp = requests.get(CONFIG_URL, auth=AUTH, headers=HEADERS)
if resp.status_code != 200:
    print(f"[ERROR] Could not retrieve topic config. HTTP {resp.status_code}: {resp.text}")
    sys.exit(1)

actual_retention = resp.json().get("value", "unknown")

# ---------------------------------------------------------------------------
# Validation summary
# ---------------------------------------------------------------------------
print()
print("=" * 50)
print("  Topic Validation Summary")
print("=" * 50)
print(f"  Topic name    : {TOPIC_NAME}")
print(f"  Partitions    : {actual_partitions}  (expected {TOPIC_PARTITIONS})")
print(f"  retention.ms  : {actual_retention}  (expected {TOPIC_RETENTION_MS})")
partitions_ok  = str(actual_partitions) == str(TOPIC_PARTITIONS)
retention_ok   = str(actual_retention)  == str(TOPIC_RETENTION_MS)
print(f"  Partitions OK : {'✅' if partitions_ok  else '❌'}")
print(f"  Retention  OK : {'✅' if retention_ok   else '❌'}")
print("=" * 50)

if not (partitions_ok and retention_ok):
    sys.exit(1)
