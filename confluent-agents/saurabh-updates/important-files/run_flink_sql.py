"""
run_flink_sql.py
Submits Flink SQL statements via the Confluent Cloud Flink SQL REST API.
Polls each statement until COMPLETED or RUNNING before submitting the next.
Statement names are suffixed with a timestamp so re-runs never collide with
previously registered statement names.
"""

import os
import sys
import time
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
    "CONFLUENT_CLUSTER_ID",
    "CONFLUENT_CLUSTER_NAME",
]

missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
if missing:
    print(f"[ERROR] Missing required environment variables: {', '.join(missing)}")
    sys.exit(1)

FLINK_API_KEY       = os.environ["FLINK_API_KEY"]
FLINK_API_SECRET    = os.environ["FLINK_API_SECRET"]
ORG_ID              = os.environ["CONFLUENT_ORG_ID"]
ENV_ID              = os.environ["CONFLUENT_ENVIRONMENT_ID"]
COMPUTE_POOL_ID     = os.environ["CONFLUENT_FLINK_COMPUTE_POOL_ID"]
CLUSTER_NAME        = os.environ["CONFLUENT_CLUSTER_NAME"]   # display name, e.g. "cluster_0"

AUTH    = (FLINK_API_KEY, FLINK_API_SECRET)
HEADERS = {"Content-Type": "application/json"}

# Confluent Flink SQL REST API base — us-east-2 AWS region endpoint
STATEMENTS_URL = (
    f"https://flink.us-east-2.aws.confluent.cloud"
    f"/sql/v1/organizations/{ORG_ID}/environments/{ENV_ID}/statements"
)

PROPERTIES = {
    "sql.current-catalog":  ENV_ID,
    "sql.current-database": CLUSTER_NAME,
}

print(f"[INFO] Flink API key    : {FLINK_API_KEY}")
print(f"[INFO] Org ID          : {ORG_ID}")
print(f"[INFO] Environment ID  : {ENV_ID}")
print(f"[INFO] Compute pool    : {COMPUTE_POOL_ID}")
print(f"[INFO] sql.current-catalog  : {ENV_ID}")
print(f"[INFO] sql.current-database : {CLUSTER_NAME}")
print()

# ---------------------------------------------------------------------------
# SQL statements — submitted in order
# ---------------------------------------------------------------------------
# Unique suffix so re-runs never collide with previously registered names
_TS = str(int(time.time()))[-6:]   # last 6 digits of epoch — short but unique

STATEMENTS = [
    (f"drop-transactions-{_TS}",    "DROP TABLE IF EXISTS `inventory.transactions`"),
    (f"create-transactions-{_TS}",  """\
CREATE TABLE `inventory.transactions` (
  sku              STRING,
  branch           STRING,
  quantity         BIGINT,
  transaction_type STRING
)
DISTRIBUTED BY HASH(sku, branch) INTO 6 BUCKETS"""),
    (f"drop-availability-{_TS}",    "DROP TABLE IF EXISTS `inventory.availability`"),
    (f"create-availability-{_TS}",  """\
CREATE TABLE `inventory.availability` (
  sku                STRING,
  branch             STRING,
  available_quantity BIGINT,
  PRIMARY KEY (sku, branch) NOT ENFORCED
)
DISTRIBUTED BY HASH(sku, branch) INTO 6 BUCKETS"""),
    (f"insert-availability-{_TS}",  """\
INSERT INTO `inventory.availability`
SELECT
  sku,
  branch,
  SUM(
    CASE
      WHEN UPPER(transaction_type) = 'ADDITION' THEN quantity
      WHEN UPPER(transaction_type) = 'SALE'     THEN -quantity
      ELSE 0
    END
  ) AS available_quantity
FROM `inventory.transactions`
GROUP BY sku, branch"""),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
TERMINAL_OK  = {"COMPLETED", "RUNNING"}
TERMINAL_ERR = {"FAILED", "DELETED", "STOPPED", "CANCELLED", "TIMEDOUT"}
POLL_INTERVAL = 3   # seconds between polls
MAX_POLLS     = 60  # ~3 min ceiling


def submit_statement(name: str, sql: str) -> str:
    """POST a SQL statement and return its statement name (used for polling)."""
    payload = {
        "name": name,
        "organization_id": ORG_ID,
        "environment_id": ENV_ID,
        "spec": {
            "statement":    sql,
            "compute_pool_id": COMPUTE_POOL_ID,
            "properties":   PROPERTIES,
        },
    }
    resp = requests.post(STATEMENTS_URL, auth=AUTH, headers=HEADERS, json=payload)
    if resp.status_code not in (200, 201):
        print(f"  [ERROR] Submit failed. HTTP {resp.status_code}: {resp.text}")
        sys.exit(1)
    data = resp.json()
    # The API returns the canonical name assigned to the statement
    return data.get("name", name)


def poll_statement(statement_name: str) -> str:
    """Poll until the statement reaches a terminal state; return that state."""
    url = f"{STATEMENTS_URL}/{statement_name}"
    for attempt in range(MAX_POLLS):
        resp = requests.get(url, auth=AUTH, headers=HEADERS)
        if resp.status_code != 200:
            print(f"  [ERROR] Poll failed. HTTP {resp.status_code}: {resp.text}")
            sys.exit(1)
        data   = resp.json()
        status = data.get("status", {}).get("phase", "UNKNOWN").upper()
        detail = data.get("status", {}).get("detail", "")
        print(f"  [POLL {attempt + 1:02d}] status={status}" + (f"  ({detail})" if detail else ""))
        if status in TERMINAL_OK:
            return status
        if status in TERMINAL_ERR:
            print(f"  [ERROR] Statement reached terminal error state: {status}")
            if detail:
                print(f"  [DETAIL] {detail}")
            sys.exit(1)
        time.sleep(POLL_INTERVAL)
    print(f"  [ERROR] Timed out waiting for statement '{statement_name}'")
    sys.exit(1)


def stop_old_streaming_jobs() -> None:
    """Stop any previously-submitted insert-availability-* jobs still RUNNING/PENDING.

    DROP TABLE only removes catalog metadata — it does not cancel a persistent
    streaming statement submitted by an earlier run. Left alone, every re-run
    of this script adds another job racing the new one to write into
    inventory.availability, each with its own stale accumulated SUM state.
    That's what caused inconsistent results across repeated runs.
    """
    url = STATEMENTS_URL
    items = []
    while url:
        resp = requests.get(url, auth=AUTH, headers=HEADERS)
        if resp.status_code != 200:
            break
        data = resp.json()
        items.extend(data.get("data", []))
        url = data.get("metadata", {}).get("next")

    stale = [
        s["name"] for s in items
        if s.get("status", {}).get("phase") in ("RUNNING", "PENDING")
        and s.get("name", "").startswith("insert-availability-")
    ]
    for name in stale:
        r = requests.delete(f"{STATEMENTS_URL}/{name}", auth=AUTH, headers=HEADERS)
        print(f"  [CLEANUP] Stopped stale streaming job '{name}': HTTP {r.status_code}")
    if not stale:
        print("  [CLEANUP] No stale streaming jobs found.")


# ---------------------------------------------------------------------------
# Main — stop stale jobs, then submit each statement sequentially
# ---------------------------------------------------------------------------
print("=" * 60)
print("STEP 0 — Stop any stale insert-availability streaming jobs")
print("=" * 60)
stop_old_streaming_jobs()
print()

for label, sql in STATEMENTS:
    print(f"{'=' * 60}")
    print(f"[SUBMIT] {label}")
    print(f"  SQL: {sql[:80].strip()}{'...' if len(sql) > 80 else ''}")

    assigned_name = submit_statement(label, sql)
    print(f"  [INFO] Statement name: {assigned_name}")

    final_status = poll_statement(assigned_name)
    print(f"  [DONE] Final status: {final_status} ✅")
    print()

print("=" * 60)
print("All Flink SQL statements submitted and verified.")
print(f"  ✅ inventory.transactions  — table ready")
print(f"  ✅ inventory.availability  — table ready")
print(f"  ✅ INSERT INTO job          — status RUNNING (continuous streaming job)")
print("=" * 60)
