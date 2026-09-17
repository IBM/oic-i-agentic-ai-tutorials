# Spec: Publish Sample Inventory Transactions

Create two deliverables:
1. `sample-transactions.json`: A dataset of 20 sample transactions.
2. `produce_messages.py`: A script to read the JSON file, publish transactions to `` `inventory.transactions` `` using the Confluent Cloud Flink REST API, and validate the inserted records.

---

## 1. Sample Data (`sample-transactions.json`)

Create a JSON array of 20 records containing **only** the 4 table columns:
- `sku` (STRING)
- `branch` (STRING)
- `quantity` (BIGINT: **strictly positive integers > 0 for all records**, whether ADDITION or SALE)
- `transaction_type` (STRING: strictly `"ADDITION"` or `"SALE"`)

**Data Distribution & Scenario Rules:**
- Include multiple records per product showing a realistic mix of `"ADDITION"` and `"SALE"` events across branches.
- Do not use negative numbers: Flink SQL handles sales subtraction internally (`WHEN 'SALE' THEN -quantity`).
- **Target Scenario (`MallOfEgypt`):**
  - `LAPTOP-DELL-XPS-15` must end with a net stock of **exactly 0** (sold out).
  - `LAPTOP-MACBOOK-PRO-16` must end with a net stock **greater than 0** (available alternative).

---

## 2. Publisher & Validation Script (`produce_messages.py`)

- Load environment variables from `.env` via `python-dotenv`.
- Read transactions from `sample-transactions.json`.
- Submit all transactions in a single Flink SQL `INSERT INTO `inventory.transactions` (`sku`, `branch`, `quantity`, `transaction_type`) VALUES (...)` statement via the Flink Statements API.
- Poll until the `INSERT` statement reaches `COMPLETED`.
- Execute a `SELECT * FROM `inventory.transactions` LIMIT 20` statement via the Flink API to confirm records are present in the table.
  - Poll until the statement reaches `RUNNING` (streaming SELECTs never reach `COMPLETED`).
  - The initial `GET /results` response always returns `data: []`; actual rows are on the **next page**. Follow the `metadata.next` URL in the response to retrieve rows, continuing to paginate until rows are returned or there are no more pages.
- Calculate and print the expected final stock balance per SKU and branch to compare against `` `inventory.availability` ``.
