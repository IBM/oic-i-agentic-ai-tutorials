"""
produce_messages.py
Publishes records from sample-transactions.json into `inventory.transactions`
via a Flink SQL INSERT INTO ... VALUES statement (Confluent Cloud Flink SQL
REST API).

Why not the Kafka REST Produce API: `inventory.transactions` is a Flink-owned
table (bare DDL, no WITH clause — Flink auto-creates the topic and
auto-registers its schema). Producing into it from outside Flink requires a
schema-aware payload type (JSONSCHEMA/AVRO/PROTOBUF) on the Kafka REST Produce
API, which was empirically confirmed to fail with a Kafka-cluster-scoped API
key alone: HTTP 422 "Schema Registry must be configured when using schemas".
Submitting the INSERT through Flink itself sidesteps that requirement
entirely, since Flink is both the schema owner and the writer.
"""

import os
import sys
import time
import json
from pathlib import Path
from collections import defaultdict

import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration — loaded exclusively from .env
# ---------------------------------------------------------------------------
REQUIRED_VARS = [
    "FLINK_API_KEY",
    "FLINK_API_SECRET",
    "CONFLUENT_ORG_ID",
    "CONFLUENT_ENVIRONMENT_ID",
    "CONFLUENT_FLINK_COMPUTE_POOL_ID",
    "CONFLUENT_CLUSTER_NAME",
    "TOPIC_NAME",
]

missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
if missing:
    print(f"[ERROR] Missing required environment variables: {', '.join(missing)}")
    sys.exit(1)

FLINK_API_KEY    = os.environ["FLINK_API_KEY"]
FLINK_API_SECRET = os.environ["FLINK_API_SECRET"]
ORG_ID           = os.environ["CONFLUENT_ORG_ID"]
ENV_ID           = os.environ["CONFLUENT_ENVIRONMENT_ID"]
COMPUTE_POOL_ID  = os.environ["CONFLUENT_FLINK_COMPUTE_POOL_ID"]
CLUSTER_NAME     = os.environ["CONFLUENT_CLUSTER_NAME"]
TOPIC_NAME       = os.environ["TOPIC_NAME"]

AUTH    = (FLINK_API_KEY, FLINK_API_SECRET)
HEADERS = {"Content-Type": "application/json"}

STATEMENTS_URL = (
    f"https://flink.us-east-2.aws.confluent.cloud"
    f"/sql/v1/organizations/{ORG_ID}/environments/{ENV_ID}/statements"
)
PROPERTIES = {"sql.current-catalog": ENV_ID, "sql.current-database": CLUSTER_NAME}

print(f"[INFO] Flink API key : {FLINK_API_KEY}")
print(f"[INFO] Topic (table) : {TOPIC_NAME}")
print()

# ---------------------------------------------------------------------------
# Load and validate sample data
# ---------------------------------------------------------------------------
# sample-transactions.json is NDJSON (one JSON object per line), not a JSON
# array. Some source records encode SALE quantities as already-negative
# numbers (e.g. -15) rather than always-positive with the sign implied by
# transaction_type. Since the Flink aggregation SQL does
# `WHEN SALE THEN -quantity`, feeding it an already-negative SALE quantity
# would double-negate it and inflate the result. Normalize every quantity to
# its absolute value here so the stored `inventory.transactions` rows always
# carry non-negative quantities, matching what the unchanged Flink SQL
# expects, regardless of how the source file encoded the sign.
DATA_FILE = Path(__file__).parent / "sample-transactions.json"
if not DATA_FILE.exists():
    print(f"[ERROR] {DATA_FILE} not found.")
    sys.exit(1)

records = []
for i, line in enumerate(DATA_FILE.read_text().splitlines()):
    line = line.strip()
    if not line:
        continue
    r = json.loads(line)
    for field in ("sku", "branch", "quantity", "transaction_type"):
        if field not in r:
            print(f"[ERROR] Record {i} missing field '{field}': {r}")
            sys.exit(1)
    if r["transaction_type"].upper() not in ("ADDITION", "SALE"):
        print(f"[ERROR] Record {i} invalid transaction_type: {r['transaction_type']}")
        sys.exit(1)
    r["quantity"] = abs(int(r["quantity"]))
    records.append(r)

print(f"[INFO] Loaded {len(records)} records from {DATA_FILE.name}")
print()

# ---------------------------------------------------------------------------
# Build and submit a single INSERT INTO ... VALUES statement
# ---------------------------------------------------------------------------
def _sql_escape(s: str) -> str:
    return s.replace("'", "''")


values_clause = ",\n  ".join(
    f"('{_sql_escape(r['sku'])}', '{_sql_escape(r['branch'])}', "
    f"{int(r['quantity'])}, '{_sql_escape(r['transaction_type'])}')"
    for r in records
)
insert_sql = (
    "INSERT INTO `inventory.transactions` (sku, branch, quantity, transaction_type) VALUES\n"
    f"  {values_clause}"
)

_TS = str(int(time.time()))[-6:]
stmt_name = f"publish-sample-data-{_TS}"

payload = {
    "name": stmt_name,
    "organization_id": ORG_ID,
    "environment_id": ENV_ID,
    "spec": {
        "statement": insert_sql,
        "compute_pool_id": COMPUTE_POOL_ID,
        "properties": PROPERTIES,
    },
}

print("[STEP] Submitting INSERT INTO `inventory.transactions` ...")
resp = requests.post(STATEMENTS_URL, auth=AUTH, headers=HEADERS, json=payload)
if resp.status_code not in (200, 201):
    print(f"[ERROR] Submit failed. HTTP {resp.status_code}: {resp.text}")
    sys.exit(1)

assigned_name = resp.json().get("name", stmt_name)
print(f"[INFO] Statement name: {assigned_name}")

# ---------------------------------------------------------------------------
# Poll until the INSERT completes
# ---------------------------------------------------------------------------
url = f"{STATEMENTS_URL}/{assigned_name}"
POLL_INTERVAL = 3
MAX_POLLS = 30

for attempt in range(MAX_POLLS):
    time.sleep(POLL_INTERVAL)
    r = requests.get(url, auth=AUTH, headers=HEADERS)
    if r.status_code != 200:
        print(f"[ERROR] Poll failed. HTTP {r.status_code}: {r.text}")
        sys.exit(1)
    data = r.json()
    phase = data.get("status", {}).get("phase", "UNKNOWN")
    detail = data.get("status", {}).get("detail", "")
    print(f"  [POLL {attempt + 1:02d}] status={phase}" + (f"  ({detail})" if detail else ""))
    if phase == "COMPLETED":
        break
    if phase in ("FAILED", "DELETED", "STOPPED", "CANCELLED"):
        print(f"[ERROR] Statement reached terminal error state: {phase}")
        if detail:
            print(f"[DETAIL] {detail}")
        sys.exit(1)
else:
    print("[ERROR] Timed out waiting for INSERT statement to complete.")
    sys.exit(1)

print(f"[OK] All {len(records)} records inserted.")
print()

# ---------------------------------------------------------------------------
# Expected final inventory (computed locally for validation guidance)
# ---------------------------------------------------------------------------
totals: dict = defaultdict(int)
for r in records:
    key = (r["sku"], r["branch"])
    qty = r["quantity"]
    if r["transaction_type"].upper() == "ADDITION":
        totals[key] += qty
    elif r["transaction_type"].upper() == "SALE":
        totals[key] -= qty

print("=" * 65)
print("  Expected inventory.availability after Flink processes all messages")
print("=" * 65)
print(f"  {'SKU':<30} {'Branch':<16} {'available_quantity':>18}")
print(f"  {'-'*30} {'-'*16} {'-'*18}")
for (sku, branch), qty in sorted(totals.items()):
    marker = " ← expected 0 ✅" if qty == 0 else (" ← above 0 ✅" if qty > 0 else " ← ⚠️  NEGATIVE")
    print(f"  {sku:<30} {branch:<16} {qty:>18}{marker}")
print("=" * 65)
print()
print("[INFO] Allow a few seconds for Flink to process and update inventory.availability.")
print("[INFO] Query via Flink SQL:  SELECT * FROM `inventory.availability`;")
