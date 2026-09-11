# Planning Analytics Agent — watsonx Orchestrate

A **watsonx Orchestrate** agent asset that connects IBM Planning Analytics (TM1) to an AI-powered agent capable of answering financial planning questions, performing variance analysis, and surfacing insights from your cube data.

---

## Overview

This asset packages everything needed to deploy a fully functioning Planning Analytics agent in watsonx Orchestrate:

| Layer | File | Purpose |
|---|---|---|
| **Agent** | `agents/pa_variance_analysis_agent.yaml` | Agent definition (LLM, instructions, starter prompts, tools) |
| **Tool** | `tools/pa_get_variance_analysis.py` | Python tool that queries TM1 via MDX and computes variance |
| **Connection** | `connections/planning_analytics_conn.yaml` | Key-value connection spec for Planning Analytics credentials |
| **Dependencies** | `tools/requirements.txt` | Python packages required by the tool |

---

## Architecture

```
watsonx Orchestrate
│
├── Agent: PA_agent_variance
│   ├── LLM: groq/openai/gpt-oss-120b
│   ├── Tool: getTotalAccountByVersionPeriod  ──► pa_get_variance_analysis.py
│   └── Tool: getSuccessFactorsData           ──► (external HR tool)
│
└── Connection: planning_analytics_test (key_value)
        address / user / password / port  ──► IBM Planning Analytics (TM1)
```

The agent accepts natural-language questions from users, determines the required account, version (Actual / Budget / Forecast), and time period, then calls the tool to fetch data directly from a TM1 cube via MDX. Results are returned as a formatted table with AI-generated insights.

---

## Repository Structure

```
.
├── agents/
│   └── pa_variance_analysis_agent.yaml   # watsonx Orchestrate agent definition
├── connections/
│   └── planning_analytics_conn.yaml      # Connection specification (key-value type)
├── tools/
│   ├── pa_get_variance_analysis.py       # Tool registered with Orchestrate
│   └── requirements.txt                  # Python dependencies
└── README.md
```

---

## Components

### Agent — `agents/pa_variance_analysis_agent.yaml`

Defines the watsonx Orchestrate native agent with:

- **Display name:** `PA_agent_variance`
- **LLM:** `groq/openai/gpt-oss-120b`
- **Tools:** `getTotalAccountByVersionPeriod`, `getSuccessFactorsData`
- **Instructions:** Guides the agent to collect account, version, and time-period parameters from the user, call the tool, and present results as a table with insights.
- **Starter prompts** — pre-built example questions surfaced to users in the chat UI:
  - *"Show me the Actual for all the entities in Jan 2025 considering Revenue"*
  - *"Explain the Forecast for the Sales Department in March 2025 for account total account"*
  - *"Show me suggestions of how to improve the Budget in Dec 2025"*
- **Welcome message:** `Hello, welcome to Planning Analytics Agent`

#### Supported Parameters

| Parameter | Example Values |
|---|---|
| Account | `Total_Account`, `Revenue`, `Operating_Expense`, `COGS` |
| Version | `Actual`, `Budget`, `Forecast` |
| Time Period | `2025_01` … `2025_12` (format: `YYYY_MM`) |

#### Example Output

```
| Entity | Department | Value    |
|--------|------------|----------|
| North  | Sales      | 52095.65 |
| North  | Finance    | 41147.18 |
| North  | HR         | 24546.96 |
```

---

### Tool — `tools/pa_get_variance_analysis.py`

A Python tool decorated with `@tool` that is registered with watsonx Orchestrate. It:

1. Builds an **MDX query** that selects Actual and Budget values for a given measure and time subset from the specified TM1 cube.
2. Establishes a **TM1Service** session using credentials retrieved from the Orchestrate key-value connection.
3. Executes the MDX query and returns a shaped **pandas DataFrame**.
4. Calculates the **Variance** (`Actual − Budget`) column.
5. Returns the result as a **list of dictionaries** (JSON-serialisable), limited to the requested number of periods.

#### Function Signature

```python
def pa_get_variance_analysis(
    measure: str = "Revenue",
    version_actual: str = "Actual",
    version_budget: str = "Budget",
    time_subset: str = "All Months",
    cube_name: str = "FinanceCube",
    limit: int = 12
) -> list[dict] | None
```

#### Credential Keys (resolved at runtime via connection)

| Key | Description |
|---|---|
| `server_host` | Planning Analytics server hostname / URL |
| `tenantid` | Cloud tenant identifier |
| `databasename` | TM1 database / server name |
| `apikey` | API key used as password |

---

### Connection — `connections/planning_analytics_conn.yaml`

Defines a **key-value** connection named `planning_analytics_test` for both `draft` and `live` environments. The connection stores Planning Analytics credentials as key-value pairs and is resolved at tool runtime via `connections.key_value(MY_APP_ID)`.

```yaml
app_id: planning_analytics_test
environments:
  draft:
    kind: key_value
    type: team
  live:
    kind: key_value
    type: team
```

---

## Prerequisites

- **IBM watsonx Orchestrate** instance with agent builder access
- **IBM Planning Analytics** (TM1) instance accessible over HTTPS
- Python **3.9+** (for local testing)
- `ibm-watsonx-orchestrate` SDK installed locally (for tool development)

---

## Setup & Deployment

### 1. Install Python dependencies (local development)

```bash
cd tools
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Register the connection

Import the connection spec into watsonx Orchestrate and populate the key-value pairs with your Planning Analytics credentials:

```bash
orchestrate connections import -f connections/planning_analytics_conn.yaml
```

Then set the credentials (example keys):

| Key | Value |
|---|---|
| `server_host` | `https://your-pa-instance.example.com` |
| `tenantid` | `your-tenant-id` |
| `databasename` | `your-tm1-database` |
| `apikey` | `your-api-key` |

### 3. Register the tool

```bash
orchestrate tools import -f tools/pa_get_variance_analysis.py -r tools/requirements.txt
```

### 4. Deploy the agent

```bash
orchestrate agents import -f agents/pa_variance_analysis_agent.yaml
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `TM1py` | Python client for IBM Planning Analytics (TM1) REST API |
| `tm1py[pandas]` | Pandas integration for TM1py (MDX → DataFrame) |
| `pandas` | Data manipulation and variance calculations |
| `python-dateutil` | Date parsing utilities |
| `keyring` | Secure credential storage (used by TM1py internally) |

---

## Related Resources

- [IBM Planning Analytics documentation](https://www.ibm.com/docs/en/planning-analytics)
- [TM1py on GitHub](https://github.com/cubewise-code/tm1py)
- [IBM watsonx Orchestrate documentation](https://www.ibm.com/docs/en/watsonx/watson-orchestrate)
