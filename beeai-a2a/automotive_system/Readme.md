# 🚗 Predictive Maintenance Automation

### Using BeeAI + Ollama + Watsonx Orchestrate + Scheduler + Agents Observability

This repository contains a complete **end-to-end predictive maintenance automation system** powered by:

* **BeeAI Framework (A2A agent with tool-calling)**
* **Ollama Granite 3.3 8B (local LLM runtime)**
* **Watsonx Orchestrate (flows, tools, agents)**
* **WXO Scheduler (recurring automation)**
* **Agents Observability (Langfuse Integration)**

The system can run:

### ✔ **Locally**

(For development, demos, offline usage, edge devices)

### ✔ **Inside Watsonx Orchestrate (SaaS)**

(For enterprise-grade scheduling, user interface, governance)

---

## Folder Structure

```
automotive_system/ 
├── agents_observability/         # Agents observability configuration (Langfuse)
│     └── langfuse_config.yml
│
├── beeai_agent/                  # BeeAI Predictive Maintenance A2A server
│     ├── __main__.py
│     ├── tools_dummy.py
│     ├── Dockerfile
│     └── pyproject.toml
│
├── beeai_host/                   # Simple BeeAI A2A client (local test tool)
│     ├── __main__.py
│     ├── Dockerfile
│     └── pyproject.toml
│
├── wxo_tools/                    # WXO Tools (Python)
│     ├── predict_failure.py
│     ├── order_parts_tool.py
│     ├── book_slot_tool.py
│     ├── maintenance_cost_tool.py
│     └── send_notification_tool.py
│
├── wxo_flows/
│     └── predictive_maintenance_flow.py
│
├── wxo_agents/
│     ├── maintenance_agent.yaml
│     └── maintenance_scheduler_agent.yaml
│
├── scripts/
│     └── import_all.sh           # Import tools + Flows + Agents to WXO + Observability
│
├── docker-compose.yml
├── maintenance_flow.py
├── maintenance_scheduler_agent.yaml
└── Readme.md
```

---

## **Requirements**

### Local Requirements

* macOS / Linux / Windows WSL2
* Python 3.11+
* Ollama installed locally
* Granite model pulled:

```bash
ollama pull granite4:3b
```

Try out with other granite model — [https://ollama.com/library/granite4](https://ollama.com/library/granite4)

* BeeAI Framework:

```bash
pip install beeai-framework 'beeai-framework[a2a]'
```

### Watsonx Orchestrate Requirements

* Watsonx Orchestrate ADK installed:

```bash
pip install ibm-watsonx-orchestrate
```

* Access to Orchestrate workspace
* API key configured (`orchestrate login`)


### **Agents Observability (Langfuse Integration)**

This system includes **agent observability** using **Langfuse**, allowing you to track:

✔ tool calls
✔ model inputs/outputs
✔ latency
✔ errors
✔ execution traces for AI Agents

#### **1. Configuration File**

The observability configuration is located here:

```
agents_observability/langfuse_config.yml
```

#### **2. Add Required Keys**

Update the file using your Langfuse project keys:

```yaml
api_key: "sk-lf-00000-00000-00000-00000-00000"
public_key: "pk-lf-00000-00000-00000-00000-00000"
```

#### **3. How It Works**

* BeeAI A2A server automatically loads the observability middleware.
* Every request/response, model call, and tool execution is reported.
* You can view insights in your **Langfuse dashboard**.

---

## **Part 1 — Run Locally (BeeAI + Ollama)**

### **1. Start Ollama**

```bash
ollama serve &
```

Test model:

```bash
ollama run granite3.3:8b "hello"
```

---

### **2. Start the BeeAI A2A Server**

```bash
cd automotive_system
python -m beeai_agent
```

Expected:

```
A2A server running on port 9999
Tools loaded: [...]
```

---

### **3. Test Using the BeeAI A2A Host**

```bash
cd automotive_system/beeai_host
python __main__.py TRUCK-22
```

You should see a complete maintenance summary.

---

## **Part 2 — Run in Watsonx Orchestrate (WXO)**

### **1. Import Everything**

```bash
cd automotive_system/scripts
./import_all.sh
```

Imports:

✔ tools
✔ flow
✔ agents (on-demand + scheduled)

---

### **2. Interact With Agent in WXO UI**

```
Run a maintenance check for TRUCK-22
```

---

### **3. Schedule Maintenance**

```
Schedule a maintenance check for TRUCK-22 every day at 9am.
```

---

## **Troubleshooting**

### Agent says “vehicle not found”

Ensure your tools have proper decorators:

```python
@tool(description="...")
```

### Server error: module not found

Run BeeAI from project root:

```
python -m beeai_agent
```

### Flow not visible in WXO

Check:

```
wxo_flows/predictive_maintenance_flow.py
```

### Scheduler not working

Ensure intrinsic tools are imported:

```
i__get_schedule_intrinsic_tool__
i__delete_schedule_intrinsic_tool__
i__get_flow_status_intrinsic_tool__
```

---

## **Conclusion**

You now have:

#### ✔ Predictive Maintenance LLM Agent (BeeAI + Granite)
#### ✔ End-to-End Workflow Automation (WXO Flow Builder)
#### ✔ Enterprise Scheduling (WXO Scheduler)
#### ✔ Local + Cloud Hybrid Setup
#### ✔ Full Observability with Langfuse

---
