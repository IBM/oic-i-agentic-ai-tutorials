# watsonx.ai RLM-Powered Custom LangGraph Agent

A custom **LangGraph** agent designed for **watsonx Orchestrate** implementing the **Scan, Delegate, and Combine** approach (Retrieval-augmented Language Model, or RLM) to process and answer questions from the [bank_loan_document.pdf](rlm_data_processor/bank_loan_document.pdf).

> [!NOTE]
> This agent is configured to be imported directly into watsonx Orchestrate using the A2A (Agent-to-Agent) protocol. The runtime configuration and credentials injection are managed by the platform via the `RunnableConfig` object.

---

## 📂 Project Structure

Below is the directory structure for this agent workspace:

```text
i-oic-custom-langgraph-rlm-agent/
├── rlm_data_processor/                       # Main agent package root
│   ├── rlm_data_processor.py                # LangGraph agent implementation code
│   ├── agent.yaml                            # watsonx Orchestrate agent metadata specification
│   ├── requirements.txt                      # Python dependencies for the agent
│   ├── bank_loan_document.pdf                # Target PDF document for queries
│   └── README.md                             # Detailed description and developer notes for the agent
└── banking_query_handler/                    # Coordinator agent package root
    └── agent.yaml                            # Coordinator agent metadata and instructions
```

### Component Details
*   **[agent.yaml](rlm_data_processor/agent.yaml)**: Declares the agent specification, including framework (`langgraph`), name, title, description, and the Python code entrypoint (`rlm_data_processor:create_agent`).
*   **[rlm_data_processor.py](rlm_data_processor/rlm_data_processor.py)**: Defines the `StateGraph` logic. It splits the document loading and querying into three sequential phases (Scan, Delegate, and Combine) to optimize LLM context usage and query performance.
*   **[bank_loan_document.pdf](rlm_data_processor/bank_loan_document.pdf)**: A 10-page sample bank loan document containing structured loan metadata, borrower information, collateral details, and terms.

---

## ⚙️ Setup & Import Instructions

Use the following commands to set up the virtual environment, activate your orchestration environment, and import the agent.

### 1. Virtual Environment Setup
Ensure you are in the project root directory and create the Python virtual environment:

```bash
# Create Python 3.11 virtual environment
python3.11 -m venv venv

# Activate the virtual environment
source venv/bin/activate
```

### 2. Activate watsonx Orchestrate Environment
Activate your target environment name (replace `<env_name>` with your actual Orchestrate environment):

```bash
orchestrate env activate <env_name>
```

### 3. Update watsonx.ai Credentials
Before importing the agent, make sure the watsonx.ai credentials in `rlm_data_processor/rlm_data_processor.py` are configured correctly:

```python
WATSONX_API_KEY = "your_watsonx_api_key"
WATSONX_PROJECT_ID = "your_watsonx_project_id"
WATSONX_URL = "your_watsonx_url"
```

### 4. Import Agents into watsonx Orchestrate
Deploy and import the agent packages:

```bash
# 1. Import RLM Sub-Agent
orchestrate agents import --experimental-package-root rlm_data_processor

# 2. Import Coordinator Agent
orchestrate agents import -f banking_query_handler/agent.yaml
```

### 5. Chat with the Agent
Open the agent chat interface to ask queries.

---

## 🧠 Sample Queries
Once deployed, you can query the agent through the chat interface about any details in the bank loan document. For every banking query, the coordinator will delegate to the RLM agent, which evaluates the document, triggers a dynamic number of parallel sub-agents (e.g., 4, 5, 6, or 8 depending on the query's hash length), and outputs the final answer followed by the execution metrics:

*   *Who is the Relationship Manager assigned to the borrower?* (Triggers parallel sub-agents processing Page 1 and Page 5)
*   *What is the loan amount, monthly salary, and collateral vehicle model?* (Aggregates multiple details across Page 3 and Page 5)
*   *What is the borrower's monthly salary and employer?*
*   *What is the final authorization code and the audit status of the document?*
