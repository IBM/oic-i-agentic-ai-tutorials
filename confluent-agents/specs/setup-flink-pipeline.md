# Real-Time Inventory with Flink SQL

Implement `run_flink_sql.py` to create and run a real-time inventory aggregation pipeline using the Confluent Cloud Flink REST API.

---

## 1. Flink SQL Pipeline

> **Note:** `` `inventory.transactions` `` and `` `inventory.availability` `` are literal table names containing dots. Always wrap them in backticks in your SQL statements.

1. **Source Table (`` `inventory.transactions` ``):**
   - Columns: `sku STRING`, `branch STRING`, `quantity BIGINT`, `transaction_type STRING`
   - Key: Hash distributed by `(sku, branch)`

2. **Sink Table (`` `inventory.availability` ``):**
   - Columns: `inventory_key STRING NOT NULL`, `sku STRING`, `branch STRING`, `available_quantity BIGINT`
   - Key: `PRIMARY KEY (inventory_key) NOT ENFORCED`, hash distributed by `inventory_key`
   - Properties: `'changelog.mode' = 'upsert'`, `'key.format' = 'raw'`, `'kafka.cleanup-policy' = 'compact'`

3. **Continuous Streaming Job:**
   - Write to `` `inventory.availability` `` grouping by `sku` and `branch`.
   - Set `inventory_key = CONCAT(sku, '|', branch)`.
   - Calculate `available_quantity`: add `quantity` for `ADDITION`, subtract for `SALE`, otherwise `0`.

---

## 2. Execution & Validation

- Create Python virtual environment.
- Load environment variables from `.env` using `python-dotenv`.
- Use the Flink Statements API (`/sql/v1/organizations/{org_id}/environments/{environment_id}/statements`) with Basic Auth.
- Set context: catalog=`CONFLUENT_ENVIRONMENT_ID`, database=`CONFLUENT_CLUSTER_NAME`, compute pool=`CONFLUENT_FLINK_COMPUTE_POOL_ID`.
- Script must be safe to re-run: check if tables exist before creating.
- Wait for `CREATE TABLE` statements to reach `COMPLETED` and the continuous `INSERT` job to reach `RUNNING`.
