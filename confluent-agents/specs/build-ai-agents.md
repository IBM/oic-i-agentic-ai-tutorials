# Spec: Deploy watsonx Orchestrate Multi-Agent Retail Assistant

Configure Confluent RTCE connectivity and deploy the multi-agent system into watsonx Orchestrate.

---

## 1. Input Collection: Real-Time Context Engine (RTCE) Details

At the start of execution, ask the user to provide the Real-Time Context Engine Topic Details.

The user will provide the details (text format), for example:
```text
"Topic Name","Environment","Cluster","Cloud","Region","Endpoint"
"inventory.availability","<YOUR_ENVIRONMENT_ID>","<YOUR_CLUSTER_ID>","<YOUR_CLOUD>","<YOUR_REGION>","https://mcp.<YOUR_REGION>.<YOUR_CLOUD>.confluent.cloud/mcp/v1/context-engine/organizations/<YOUR_ORG_ID>/environments/<YOUR_ENVIRONMENT_ID>/kafka-clusters/<YOUR_CLUSTER_ID>"
```

- Extract the `Endpoint` URL as `RTCE_MCP_URL` from the user response.
- Map credentials from `.env` using the following exact keys:
  - **Username / API Key:** `FLINK_API_KEY`
  - **Password / API Secret:** `FLINK_API_SECRET`
  *(Note: Confluent RTCE endpoints authenticate using the Confluent Cloud Flink API credentials).*

---

## 2. Confluent RTCE Connection & MCP Toolkit

1. **Connection (`confluent_rtce`):**
   - Add team-level connection named `confluent_rtce` using `orchestrate connections add -a confluent_rtce` (or YAML declaration).
   - Configure for `draft` environment (and `live` if deployed on SaaS/Cloud environments) using `basic` authentication against `RTCE_MCP_URL`. In local Developer Edition, only `draft` is supported.
   - Set credentials with `FLINK_API_KEY` (username) and `FLINK_API_SECRET` (password) loaded from `.env`:
     ```bash
     orchestrate connections set-credentials -a confluent_rtce --env draft -u "$FLINK_API_KEY" -p "$FLINK_API_SECRET"
     ```

2. **Toolkit (`confluent-rtce`):**
   - Register remote MCP toolkit `confluent-rtce` via `streamable_http` transport pointing to `RTCE_MCP_URL`.
   - Expose tools: `listTopics,getMetadata,queryData`.
   - Link to connection `confluent_rtce`.

---

## 3. Knowledge Base (`enterprise_documents`)

- Create and import knowledge base `enterprise_documents` containing `knowledge-bases/product-catalog.txt`.
- Check status (`orchestrate knowledge-bases status -n enterprise_documents`) to confirm `Ready` is `True` before deploying referencing agents.

---

## 4. Agent Declarations (`agents/`)

Create three AI agents:

1. **`SKU_Availability_Agent` (`agents/SKU_Availability_Agent.yaml`):**
   - **Role:** Authoritative assistant for real-time stock availability across branches.
   - **Style:** `react_core`
   - **Tools:** `confluent-rtce:listTopics`, `confluent-rtce:getMetadata`, `confluent-rtce:queryData`.
   - **Instructions & Operational Guidelines:**
     - Treat Confluent Real-Time Context Engine (RTCE) as the sole authoritative source for live inventory.
     - Use `listTopics` when confirming available RTCE-enabled topics.
     - Call `getMetadata` on `inventory.availability` before running queries to verify column names and types.
     - Query `inventory.availability` using `queryData` filtered by the requested `sku` and `branch`. Select only required columns and keep result limits small.
     - Do not perform `SUM`, `COUNT`, `GROUP BY`, joins, or aggregations in RTCE queries; Apache Flink already computes `available_quantity`.
     - Status evaluation:
       - If `available_quantity > 0`, return status `IN_STOCK` and state the available count.
       - If `available_quantity == 0`, return status `OUT_OF_STOCK`.
       - If no matching row exists, state that the item is not tracked (never hallucinate quantities).
     - For branch-wide stock inquiries, return and summarize only records where `available_quantity > 0`.

2. **`Substitute_Finder_Agent` (`agents/Substitute_Finder_Agent.yaml`):**
   - **Role:** Recommends 2–3 alternative products when requested SKU is unavailable.
   - **Style:** `react_core`
   - **Knowledge Base:** `enterprise_documents`.
   - **Instructions:** Perform Agentic RAG semantic search over catalog attributes (category, processor, specs, price tier). Justify recommendations based strictly on catalog data.

3. **`Store_Associate_Agent` (`agents/Store_Associate_Agent.yaml`):**
   - **Role:** Supervisor agent coordinating the specialist agents for store staff.
   - **Style:** `react_core`
   - **Collaborators:** `SKU_Availability_Agent`, `Substitute_Finder_Agent`.
   - **Decision Flow:**
     1. Delegate to `SKU_Availability_Agent` to check availability at target branch.
     2. If in stock, return available quantity.
     3. If out of stock, immediately delegate to `Substitute_Finder_Agent` to suggest 2–3 alternatives.

---

## 5. Import & End-to-End Validation

1. **Deployment Order:** Import connection -> toolkit -> knowledge base -> specialist agents (`SKU_Availability_Agent`, `Substitute_Finder_Agent`) -> supervisor agent (`Store_Associate_Agent`).
2. **Specialist Verification (`SKU_Availability_Agent`):**
   - **Discovery:** *"What topics are available?"* -> confirms `inventory.availability` is listed.
   - **Metadata:** *"Describe inventory.availability"* -> confirms schema (`key`, `sku`, `branch`, `available_quantity`).
   - **Point Lookup:** *"What is the availability of LAPTOP-DELL-XPS-15 in MallOfEgypt?"* -> returns `OUT_OF_STOCK` (quantity 0).
   - **Branch Lookup:** *"What are the available SKUs in MallOfEgypt?"* -> lists available branch items (e.g. `LAPTOP-MACBOOK-PRO-16`).
3. **Supervisor Flow Test (`Store_Associate_Agent`):**
   - Ask: *"Do you have LAPTOP-DELL-XPS-15 in MallOfEgypt?"* -> confirms item is out of stock and provides 2–3 catalog alternatives.
   - Ask: *"Do you have LAPTOP-MACBOOK-PRO-16 in MallOfEgypt?"* -> confirms in-stock status with available count.
