"""
get_sku_availability.py
MCP server — Real-time inventory availability checker.

Exposes one tool:
    get_sku_availability(sku: str, branch: str) -> dict
    get_all_availability() -> list[dict]

Reads the current aggregated state from the Confluent Cloud
inventory.availability Kafka topic (computed by Apache Flink from
inventory.transactions) via the Flink SQL REST API.

Run as an MCP server:
    python3 get_sku_availability.py

Import into watsonx Orchestrate:
    orchestrate toolkits add \
        --kind mcp \
        --name "sku-availability-checker" \
        --description "Real-time inventory availability checker using Confluent Kafka and Apache Flink" \
        --language python \
        --package-root "<absolute-path-to-confluent-tutorial>" \
        --command "python3 get_sku_availability.py" \
        --tools "*"
"""

import os
import sys
import time
import json
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

# ── MCP SDK ───────────────────────────────────────────────────────────────────
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    try:
        from fastmcp import FastMCP
    except ImportError:
        print("[ERROR] 'mcp' package not found. Run: pip install mcp", file=sys.stderr)
        sys.exit(1)

# ── Load .env / .env.tutorial (local dev only) ────────────────────────────────
for _env_file in (".env", ".env.tutorial"):
    _path = os.path.join(os.path.dirname(__file__), _env_file)
    if os.path.exists(_path):
        load_dotenv(dotenv_path=_path)
        break

FLINK_KEY    = os.environ.get("FLINK_API_KEY", "")
FLINK_SECRET = os.environ.get("FLINK_API_SECRET", "")
ORG_ID       = os.environ.get("CONFLUENT_ORG_ID", "")
ENV_ID       = os.environ.get("CONFLUENT_ENVIRONMENT_ID", "")
POOL_ID      = os.environ.get("CONFLUENT_FLINK_COMPUTE_POOL_ID", "")
DB_NAME      = os.environ.get("CONFLUENT_CLUSTER_NAME", "cluster_0")
FLINK_API_URL = os.environ.get("FLINK_API_URL", "").rstrip("/")

# Credentials resolved lazily — injected as env vars by the WXO key_value connection at runtime.
# Do not exit at module load; fail at tool-call time if missing.
FLINK_BASE = f"{FLINK_API_URL}/organizations/{ORG_ID}/environments/{ENV_ID}" if FLINK_API_URL and ORG_ID and ENV_ID else ""
AUTH    = HTTPBasicAuth(FLINK_KEY, FLINK_SECRET)
HEADERS = {"Content-Type": "application/json"}

# ── MCP server ────────────────────────────────────────────────────────────────
mcp = FastMCP(
    name="sku-availability-checker",
    instructions=(
        "Use get_sku_availability to check if a specific SKU is in stock at a branch. "
        "Use get_all_availability to list every SKU and quantity across all branches."
    ),
)

# ── Helper: submit SELECT + follow pagination ─────────────────────────────────

def _run_flink_select(sql: str) -> list[list]:
    """Submit a Flink SQL SELECT and return all op=0 / op=2 (latest) rows as lists."""
    if not all([FLINK_KEY, FLINK_SECRET, ORG_ID, ENV_ID, POOL_ID, FLINK_API_URL]):
        raise RuntimeError("Missing Flink credentials. Ensure the confluent_sku_creds connection is configured with all required env vars.")
    stmt_name = f"mcp-{int(time.time() * 1000) % 1_000_000}"
    payload = {
        "name": stmt_name,
        "spec": {
            "statement": sql,
            "properties": {
                "sql.current-catalog":  ENV_ID,
                "sql.current-database": DB_NAME,
            },
            "compute_pool_id": POOL_ID,
        },
    }

    r = requests.post(f"{FLINK_BASE}/statements", auth=AUTH, headers=HEADERS, json=payload, timeout=15)
    r.raise_for_status()

    # Poll for RUNNING
    for _ in range(10):
        time.sleep(2)
        sr = requests.get(f"{FLINK_BASE}/statements/{stmt_name}", auth=AUTH, headers=HEADERS, timeout=10)
        phase = sr.json().get("status", {}).get("phase", "PENDING")
        if phase in ("RUNNING", "COMPLETED"):
            break

    # Follow pagination — collect all rows, keep only the latest value per key
    url = f"{FLINK_BASE}/statements/{stmt_name}/results"
    latest: dict[tuple, list] = {}
    seen_any = False

    for _ in range(8):
        time.sleep(1)
        rr = requests.get(url, auth=AUTH, headers=HEADERS, timeout=10)
        if rr.status_code != 200:
            break
        data   = rr.json()
        rows   = data.get("results", {}).get("data", [])
        if rows:
            seen_any = True
            for row in rows:
                op     = row.get("op", 0)
                fields = row.get("row", [])
                if len(fields) >= 2:
                    key = tuple(fields[:2])          # (sku, branch)
                    if op in (0, 2):                 # INSERT or UPDATE_AFTER
                        latest[key] = fields
                    elif op in (1,):                 # UPDATE_BEFORE — remove stale
                        latest.pop(key, None)

        next_url = data.get("metadata", {}).get("next")
        if next_url and not seen_any:
            url = next_url
        elif seen_any:
            # Follow next once more to catch remaining rows, then stop
            if next_url:
                url = next_url
                continue
            break

    return list(latest.values())


# ── Tool 1: get_sku_availability ──────────────────────────────────────────────

@mcp.tool()
def get_sku_availability(sku: str, branch: str) -> dict:
    """
    Get the current real-time inventory availability for a specific SKU at a branch.

    Queries the inventory.availability Kafka topic that is continuously updated
    by an Apache Flink aggregation pipeline running on Confluent Cloud.

    Args:
        sku:    Product SKU identifier, e.g. "LAPTOP-DELL-XPS-15"
        branch: Store branch name, e.g. "MallOfEgypt" or "DubaiMall"

    Returns:
        dict with keys:
            sku              – the queried SKU
            branch           – the queried branch
            available_quantity – integer quantity (0 = out of stock)
            status           – "IN_STOCK" or "OUT_OF_STOCK"
            source           – "confluent_kafka_flink"
    """
    sql = (
        f"SELECT sku, branch, available_quantity "
        f"FROM `inventory.availability` "
        f"WHERE sku = '{sku}' AND branch = '{branch}';"
    )

    try:
        rows = _run_flink_select(sql)
    except Exception as exc:
        return {"error": str(exc), "sku": sku, "branch": branch}

    if not rows:
        return {
            "sku": sku,
            "branch": branch,
            "available_quantity": 0,
            "status": "NOT_FOUND",
            "source": "confluent_kafka_flink",
        }

    _, _, qty = rows[0][0], rows[0][1], rows[0][2]
    available = int(qty)
    return {
        "sku": sku,
        "branch": branch,
        "available_quantity": available,
        "status": "IN_STOCK" if available > 0 else "OUT_OF_STOCK",
        "source": "confluent_kafka_flink",
    }


# ── Tool 2: get_all_availability ──────────────────────────────────────────────

@mcp.tool()
def get_all_availability() -> list:
    """
    Get the current real-time inventory availability for ALL SKUs across ALL branches.

    Queries the inventory.availability Kafka topic that is continuously updated
    by an Apache Flink aggregation pipeline running on Confluent Cloud.

    Returns:
        list of dicts, each with:
            sku              – product SKU
            branch           – store branch
            available_quantity – current quantity
            status           – "IN_STOCK" or "OUT_OF_STOCK"
    """
    sql = "SELECT sku, branch, available_quantity FROM `inventory.availability`;"

    try:
        rows = _run_flink_select(sql)
    except Exception as exc:
        return [{"error": str(exc)}]

    results = []
    for row in sorted(rows, key=lambda r: (r[1], r[0])):  # sort by branch, then sku
        sku, branch, qty = row[0], row[1], row[2]
        available = int(qty)
        results.append({
            "sku": sku,
            "branch": branch,
            "available_quantity": available,
            "status": "IN_STOCK" if available > 0 else "OUT_OF_STOCK",
        })

    return results


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run()
