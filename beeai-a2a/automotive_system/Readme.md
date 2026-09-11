# 🚗 Predictive Maintenance Automation
### A Production-Grade Enterprise Agentic AI Demo - Multi-Agent, Observable, Framework-Agnostic and Scalable
#### BeeAI + IBM watsonx + IBM Granite Model + watsonx Orchestrate (Agentic Workflow + External Agents) + Langfuse (Observability)

[![IBM watsonx](https://img.shields.io/badge/IBM-watsonx-blue)](https://www.ibm.com/watsonx)
[![BeeAI Agentic Framework](https://img.shields.io/badge/BeeAI-Framework-green)](https://github.com/i-am-bee/bee-agent-framework)
[![Granite Models](https://img.shields.io/badge/Granite-4.0-orange)](https://www.ibm.com/granite)
[![watsonx Orchestrate](https://img.shields.io/badge/watsonx-Orchestrate-purple)](https://www.ibm.com/watsonx/orchestrate)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [System Architecture](#-system-architecture)
- [Key Features](#-key-features)
- [Prerequisites](#-prerequisites)
- [Project Structure](#-project-structure)
- [Understanding the Code](#-understanding-the-code)
- [Local Setup](#-local-setup)
- [IBM Code Engine Deployment](#-ibm-code-engine-deployment)
- [watsonx Orchestrate Integration](#-watsonx-orchestrate-integration)
- [Observability with Langfuse](#-observability-with-langfuse)
- [Testing](#-testing)
- [API Reference](#-api-reference)
- [Support & Resources](#-support--resources)
- [Authors](#-authors)

---

## 🎯 Overview

This project demonstrates a **production-ready AI agent integration** for predictive vehicle maintenance, combining five enterprise technologies: 

| Technology | Role |
|------------|------|
| **🤖 BeeAI Framework** | Agentic AI with tool orchestration |
| **🧠 IBM watsonx** | Enterprise LLM platform and infrastructure |
| **💎 Granite Models** | High-performance instruction-following model |
| **🔗 watsonx Orchestrate** | Workflow automation and agent management |
| **📊 Langfuse** | End-to-end AI observability and tracing |

### What This System Does

- ✅ **Predicts** vehicle component failures before they happen
- ✅ **Analyzes** real-time data: vehicle location, driver availability, service slots, parts inventory
- ✅ **Orchestrates** end-to-end workflows: predict → estimate cost → order parts → book service → notify driver
- ✅ **Integrates** WXO native agents with external BeeAI agent over HTTP
- ✅ **Traces** every agent decision, tool call, and LLM interaction

---

## 🏗️ System Architecture

![Architecture Diagram](docs/architecture-diagram.gif)

### Data Flow

```
User Query: "Check maintenance for TRUCK-22"
    ↓
watsonx Orchestrate (maintenance_agent)
    ├─→ Calls: BeeAI external agent (HTTP POST /chat/completions)
    │     ↓
    │   BeeAI Service (FastAPI)
    │     ├─→ Tool 1: get_vehicle_location("TRUCK-22") → San Francisco
    │     ├─→ Tool 2: get_driver_schedule("driver-1") → Available 2025-11-22 14:00
    │     ├─→ Tool 3: get_dealership_slots("San Francisco") → Slot 2025-11-22 15:00
    │     ├─→ Tool 4: get_parts_inventory("Brake Pads") → Stock: 5 units
    │     └─→ LLM Request → IBM watsonx.ai (Granite)
    │           └─→ Synthesizes comprehensive response
    │
    └─→ May trigger: predictive_maintenance_flow
          ├─→ predict_failure
          ├─→ check_maintenance_cost
          ├─→ order_parts
          ├─→ book_service_slot
          └─→ notify_driver
    ↓
Langfuse captures full trace (all steps, timings, tokens, costs)
    ↓
User receives: Complete maintenance plan with booking details
```

### Integration Points

| From | To | Protocol | Description |
|------|-----|----------|-------------|
| WXO Agent | BeeAI Service | HTTP POST | External agent integration |
| BeeAI | watsonx.ai | REST API | LLM inference requests |
| All Services | Langfuse | OpenTelemetry | Trace collection |
| WXO Scheduler | WXO Flow | Internal | Recurring automation |

---

## ✨ Key Features

### BeeAI Service

- 🎯 **Requirement Agent**: Enforces tool execution order
- 🔧 **Tool Collection**: 4 predictive maintenance tools (location, schedule, slots, inventory)
- 💾 **Memory Management**: Full conversation context retention
- 📝 **Trajectory Logging**: Complete execution tracking
- 🌐 **WXO-Compatible API**: OpenAI-style `/chat/completions` endpoint

### IBM watsonx & Granite Models

- 💎 **Granite Models**: High-performance instruction-following model optimized for enterprise workloads
- ⚡ **Low Latency**: ~200ms inference time for typical requests
- 🔧 **Tool Calling**: Native support for function/tool invocation
- 📏 **Context Window**: 8,192 tokens for comprehensive context understanding
- 💰 **Cost-Effective**: Cheaper than GPT-3.5 and other LLMs with comparable performance
- 🌍 **Enterprise-Grade**: SLA guarantees, multi-region deployment, compliance-ready (GDPR, SOC2, HIPAA)

### watsonx Orchestrate Integration

- 🤖 **Native Agents**: maintenance_agent, scheduler_agent
- 🔀 **Workflows**: 5-step predictive maintenance flow
- 🔧 **Tools**: predict_failure, cost_estimation, parts_ordering, booking, notifications
- 🔗 **External Agent**: Calls BeeAI over HTTP with API key authentication
- ⏰ **Scheduler**: Recurring maintenance checks (daily, weekly, cron-based)

### Observability

- 📊 **Full Tracing**: Every request, tool call, LLM interaction
- 💰 **Cost Tracking**: Token usage and cost per request
- ⏱️ **Performance**: Latency breakdown by component
- 🔍 **Debug**: Step-by-step execution viewer
- 📈 **Analytics**: Usage trends, success rates, error patterns

---

## 📦 Prerequisites

### Required Accounts

1. **IBM Cloud Account**
   - watsonx.ai service provisioned
   - Project created with Granite model access
   - API key generated

2. **watsonx Orchestrate**
   - Subscription active
   - ADK installed: `pip install ibm-watsonx-orchestrate`

3. **Langfuse (Optional)**
   - Free account at [cloud.langfuse.com](https://cloud.langfuse.com)
   - Project created
   - API keys obtained

### Development Tools

- Python 3.11+
- Docker or Podman
- Git
- curl (for testing)

---

## 📂 Project Structure

```
.
├── beeai_service/              # Main BeeAI service
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py         # Pydantic settings (env vars)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py            # BeeAI RequirementAgent setup
│   │   └── tools.py            # Tool definitions
│   ├── servers/
│   │   ├── __init__.py
│   │   └── wxo_server.py       # FastAPI WXO-compatible server
│   ├── __init__.py
│   ├── __main__.py             # Entry point
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── pyproject.toml          # Package dependencies and version pins
│   ├── setup_local.sh          # Local development setup
│   └── deploy_to_code_engine.sh # IBM Code Engine deployment
│
├── agents_observability/
│   └── langfuse_config.yml     # Langfuse configuration
│
├── wxo_tools/                  # watsonx Orchestrate tools
│   ├── predict_failure.py
│   ├── maintenance_cost_tool.py
│   ├── book_slot_tool.py
│   ├── order_parts_tool.py
│   └── send_notification_tool.py
│
├── wxo_flows/                  # watsonx Orchestrate flows
│   └── predictive_maintenance_flow.py
│
├── wxo_agents/                 # watsonx Orchestrate agents
│   ├── maintenance_agent.yaml
│   └── maintenance_scheduler_agent.yaml
│
├── scripts/
│   └── import_all.sh           # Import everything to WXO
│
├── docs/                       # Screenshots and diagrams
│
└── README.md                   # This file
```

---

## 🔍 Understanding the Code

### 3. BeeAI Tools

The BeeAI agent uses four predictive maintenance tools defined in [beeai_service/core/tools.py](beeai_service/core/tools.py). These tools provide real-time situational awareness:

| Tool | Purpose |
|------|---------|
| `get_vehicle_location` | Returns the current city for a given vehicle ID |
| `get_driver_schedule` | Returns driver availability windows |
| `get_dealership_slots` | Returns available service slots in a given city |
| `get_parts_inventory` | Checks inventory count for a specific component |

Each tool is decorated with `@tool` from the BeeAI framework and returns a structured dictionary. All four tools are exported as `ALL_TOOLS` for the agent to use.

> **Note:** For this tutorial, the tools return simulated data to demonstrate the integration end-to-end. For example, `get_vehicle_location` always returns San Francisco, and `get_parts_inventory` always returns a stock of 5. In a production system, you would replace these with real API calls to your fleet management, scheduling, and inventory systems.

### 4. BeeAI Agent

The core agent logic lives in [beeai_service/core/agent.py](beeai_service/core/agent.py). It creates a `RequirementAgent` from the BeeAI framework that:

- Connects to IBM watsonx.ai using the Granite 4 model (`ibm/granite-4-h-small`)
- Enforces a strict tool execution order using `ConditionalRequirement` — ensuring `get_vehicle_location` is always called first
- Uses `GlobalTrajectoryMiddleware` for complete execution tracking
- Maintains full conversation context with `UnconstrainedMemory`

The agent instructions define a clear workflow: locate the vehicle → check driver availability → find dealership slots → verify parts inventory → synthesize a recommendation.

### 5. WXO-Compatible Server

The FastAPI server in [beeai_service/servers/wxo_server.py](beeai_service/servers/wxo_server.py) is what makes BeeAI accessible to watsonx Orchestrate. It exposes the following endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/completions` | POST | Main endpoint — receives chat messages, runs the agent, returns SSE stream |
| `/health` | GET | Health check returning service status, model name, and timestamp |
| `/.well-known/agent-card.json` | GET | A2A protocol discovery card with agent metadata |

The server authenticates requests via the `x-api-key` header and returns results as Server-Sent Events (SSE) — the format WXO expects for streaming responses.

The agent card (`/.well-known/agent-card.json`) advertises the agent's capabilities to WXO, including `"streaming": true` and `"function_calling": false`. The `function_calling: false` flag is important — BeeAI handles all tool orchestration internally via the `RequirementAgent`, rather than exposing tools as OpenAI-style function calls.

The entry point that wires everything together is [beeai_service/__main__.py](beeai_service/__main__.py) — it creates the agent, wraps it in the WXO server, and starts serving.

---

## 🚀 Local Setup

### Step 1: Clone Repository

```bash
git clone https://github.com/IBM/oic-i-agentic-ai-tutorials.git
cd beeai-a2a/automotive_system
cd beeai_service
```

### Step 2: Configure Environment

Copy the provided template and update with your credentials:
```bash
cp env.example .env
```
The template `.env` file is available in the repository. Only the values wrapped inside `< >` need to be replaced:

```bash
# BeeAI Service Configuration
# Server Configuration
BEEAI_WXO_PORT=8080
BEEAI_WXO_HOST=0.0.0.0
BEEAI_API_KEY=beeai-maintenance-key-2024

# LLM Configuration
BEEAI_LLM_MODEL=watsonx:ibm/granite-4-h-small

# Logging
BEEAI_LOG_LEVEL=INFO
BEEAI_LOG_INTERMEDIATE_STEPS=false

# IBM watsonx.ai Configuration
WATSONX_API_KEY=<your-watsonx-api-key>
WATSONX_URL=<your-watsonx-url>
WATSONX_PROJECT_ID=<your-watsonx-project-id>
WATSONX_MODEL_ID=ibm/granite-4-h-small
WATSONX_MAX_TOKENS=4096
WATSONX_TEMPERATURE=0.7
```

⚠️ **Note**: Replace `your-watsonx-api-key`, `your-watsonx-url` and `your-watsonx-project-id` with your actual credentials.

	
### Step 3: Install Podman (Prerequisite)
The setup script uses Podman and Podman Compose to build and run the container. On macOS, install using Homebrew:
```bash
cd beeai_service
brew install podman podman-compose
```

### Step 4: Start BeeAI Service
```bash
chmod +x setup_local.sh
./setup_local.sh
```

**Expected Output:**

![BeeAI Local Startup](docs/beeai-local-startup.png)

You should see:
- ✅ Container built and started
- ✅ Model loaded: `watsonx:ibm/granite-4-h-small`
- ✅ Tools loaded: 4
- ✅ Agent initialized successfully
- ✅ Server running at `http://localhost:8080`

### Step 5: Test Local Deployment

#### Health Check

```bash
curl http://localhost:8080/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "service": "BeeAI Predictive Maintenance",
  "model": "watsonx:ibm/granite-4-h-small",
  "timestamp": 1708312800
}
```

#### Test Agent (Streaming)

```bash
curl -X POST http://localhost:8080/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-api-key: beeai-maintenance-key-2024" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "Check maintenance status for vehicle TRUCK-22"
      }
    ],
    "stream": true
  }'
```

**Expected Response** (SSE stream):
```
data: {"id":"chatcmpl-beeai-xxx","choices":[{"delta":{"content":"Vehicle TRUCK-22 is currently located in San Francisco..."}}]}
...
data: [DONE]
```

### Step 6: View Logs

```bash
# Docker
docker compose logs -f

# Podman
podman compose logs -f
```

---

## ☁️ IBM Code Engine Deployment

### Step 1: Update `.env` with IBM Cloud Credentials

Add these to your `.env` file. Only the values wrapped inside `< >` need to be replaced:

```bash
# IBM Cloud Configuration for Deployment
IBM_CLOUD_API_KEY=<your-ibm-cloud-api-key>
NAMESPACE=<your-container-registry-namespace>
IMAGE_NAME=beeai_maintenance_service
IMAGE_TAG=v1
APP_NAME=beeai-maintenance
PROJECT_ID=<your-code-engine-project-id>
RESOURCE_GROUP=<your-resource-group>
REGION=<your-region>
```

⚠️ **Note**: Replace `=your-ibm-cloud-api-key`, `your-container-registry-namespace`, `your-code-engine-project-id`, `your-region` and `your-resource-group` with your actual credentials.

### Step 2: Deploy to Code Engine

```bash
cd beeai_service
chmod +x deploy_to_code_engine.sh
./deploy_to_code_engine.sh
```

**Deployment Steps Performed:**
1. ✅ Login to IBM Cloud
2. ✅ Build container image (linux/amd64)
3. ✅ Push to IBM Container Registry
4. ✅ Create/update Code Engine application
5. ✅ Configure environment variables
6. ✅ Set up health checks
7. ✅ Get public URL

#### View logs

```bash
ibmcloud ce app logs --name beeai-maintenance --follow
```

**Expected Output:**

![Code Engine Deployment](docs/beeai-code-engine.png)

### Step 3: Get Application URL

```bash
ibmcloud ce app get --name beeai-maintenance
```

**Example URL:**
```
https://beeai-maintenance.261z8nqmth9f.us-south.codeengine.appdomain.cloud
```

### Step 4: Test Deployed Service

```bash
curl -X POST https://beeai-maintenance.261z8nqmth9f.us-south.codeengine.appdomain.cloud/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-api-key: beeai-maintenance-key-2024" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "Check maintenance status for vehicle TRUCK-22"
      }
    ],
    "stream": true
  }'
```

### Useful Commands

```bash
# View logs
ibmcloud ce app logs --name beeai-maintenance --follow

# Get status
ibmcloud ce app get --name beeai-maintenance

# Scale
ibmcloud ce app update --name beeai-maintenance --min-scale 2 --max-scale 5

# Delete
ibmcloud ce app delete --name beeai-maintenance --force
```

---

## 🔗 watsonx Orchestrate Integration

### Step 1: Authenticate with WXO Environment

First, activate your watsonx Orchestrate environment:
```bash
orchestrate env activate <your_environment_name> --api-key <your_api_key>
```
⚠️ **Note**: Replace `your_environment_name` and `your_api_key` with your actual WXO environment credentials.

### Step 2: Configure Langfuse Before Importing
Before running the import script, update `agents_observability/langfuse_config.yml` with your Langfuse credentials so observability is active from the first agent run:
```yaml
spec_version: v1
kind: langfuse
project_id: predictive-maintenance-fleet
api_key: "sk-lf-<your-secret-key>"
url: "https://cloud.langfuse.com/api/public/otel"
host_health_uri: "https://cloud.langfuse.com"
config_json:
  public_key: "pk-lf-<your-public-key>"
  mask_pii: false
```
> Don't have a Langfuse account yet? Sign up free at [cloud.langfuse.com](https://cloud.langfuse.com), create a project, and copy your keys from **Settings → API Key & Public Key**. 

### Step 3: Import All Components
```bash
cd scripts
chmod +x import_all.sh
./import_all.sh
```

This imports:
- ✅ 5 WXO Tools (predict, cost, order, book, notify)
- ✅ 1 Workflow (predictive_maintenance_flow)
- ✅ 2 Agents (maintenance_agent, scheduler_agent)
- ✅ Langfuse observability configuration

### Step 4: Register BeeAI as External Agent

#### WXO UI

1. **Navigate to**: watsonx Orchestrate → Agents → Import agent

![Import Agent Type](docs/wxo-import-agent-type.png)

2. **Select**: External agent → Next

3. **Configure Agent Details**:

![Agent Details](docs/beeai-wxo-agent-details.png)

| Field | Value |
|-------|-------|
| **External protocol** | External agent via chat completion |
| **Authentication type** | API key |
| **API key** | `beeai-maintenance-key-2024` |
| **External agent's URL** | `https://beeai-maintenance.xxx.codeengine.appdomain.cloud/chat/completions` |
| **Display name** | `beeai_predictive_maintenance_agent` |
| **Description** | An AI-powered predictive maintenance agent for fleet vehicles that analyzes maintenance requirements and provides real-time operational insights, including vehicle location tracking, driver availability and schedules, dealership service slot availability, and parts inventory verification. |

4. **Import agent** → Done

### Step 5: Test Integration

**In WXO Chat:**
```
Can you help me check vehicle TRUCK-22
```

**Expected Flow:**

![WXO Agent Preview](docs/wxo-agent-preview.png)

The agent will:
1. ✅ Call BeeAI external agent
2. ✅ Receive real-time analysis (location, driver, slots, parts)
3. ✅ May trigger predictive_maintenance_flow
4. ✅ Return comprehensive maintenance plan with booking reference

**Example Response:**
```
Vehicle TRUCK-22 is currently located in San Francisco. The driver, driver-1, 
is available on 2025-11-22 from 14:00. The earliest available dealership slot 
for service is on 2025-11-22 at 15:00. The parts inventory for Brake Pads is 
available. 

Recommended action plan: Schedule the vehicle for service at the earliest 
available slot on 2025-11-22 at 15:00.

The service has been scheduled successfully.

Booking Reference: BOOK-TRUCK-22-2025-11-22T15-00-00
Vehicle: TRUCK-22
Service: Brake Pads maintenance (due in 7 days)
Scheduled Time: 2025-11-22 at 15:00 (local time)
Driver Notified: driver-1
```
---

## 📊 Observability with Langfuse

Langfuse provides full observability for the agentic workflow, allowing you to inspect every step of execution including LLM reasoning, tool usage, latency, and cost.

###  Viewing Traces

To inspect traces generated by the system:

1. Open the **Langfuse Dashboard**  
   👉 https://cloud.langfuse.com

2. Select your project  
   Example: `predictive-maintenance-fleet`

3. Navigate to the **Traces** section.

4. Select a trace generated from a **watsonx Orchestrate agent interaction**.

Each trace represents a **complete end-to-end execution** of the agentic workflow, including all intermediate reasoning steps and tool invocations.

**Expected Trace**

![Langfuse Trace](docs/langfuse-trace.png)

### 📦 What Gets Captured

Langfuse automatically records detailed telemetry for every workflow execution, including:

- ✅ **User Query** – The original input request from the user
- ✅ **Agent Metadata** – Agent name, version, and execution context
- ✅ **Tool Calls** – All tool invocations with parameters and responses
- ✅ **LLM Calls** – Model inputs, outputs, token usage, and cost
- ✅ **Execution Timing** – Latency for each step in the workflow
- ✅ **Total Request Latency** – Full end-to-end execution time
- ✅ **Error Traces** – Any failures encountered during execution

This observability layer makes it easy to:

- Debug agent workflows
- Monitor LLM performance and cost
- Track tool execution
- Analyze latency bottlenecks
- Improve system reliability

---

## 🧪 Testing

### Test 1: Local Health Check

```bash
curl http://localhost:8080/health
```

**Expected**: HTTP 200 + JSON response with service status

### Test 2: Local Agent Test

```bash
curl -X POST http://localhost:8080/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-api-key: beeai-maintenance-key-2024" \
  -d '{
    "messages": [{"role": "user", "content": "Check TRUCK-22"}],
    "stream": false
  }'
```

**Expected**: JSON response with vehicle analysis

### Test 3: Code Engine Test

```bash
curl -X POST https://your-app-url.codeengine.appdomain.cloud/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-api-key: beeai-maintenance-key-2024" \
  -d '{
    "messages": [{"role": "user", "content": "Check TRUCK-22"}],
    "stream": false
  }'
```

**Expected**: JSON response from cloud deployment

### Test 4: WXO Integration

**In WXO Chat:**
```
Run a maintenance check for TRUCK-22
```

**Expected**:
- ✅ Agent calls BeeAI external agent
- ✅ Receives comprehensive analysis
- ✅ May trigger workflow
- ✅ Returns booking details

### Test 5: Scheduler

**In WXO Chat:**
```
Schedule daily maintenance checks for TRUCK-22 at 9am EST
```

**Verify:**
```bash
orchestrate schedules list
```

**Expected**:
- ✅ Schedule created
- ✅ Cron pattern: `0 9 * * *`
- ✅ Timezone: America/New_York

---

## 📚 API Reference

### Endpoints

#### 1. Health Check

```
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "BeeAI Predictive Maintenance",
  "model": "watsonx:ibm/granite-4-h-small",
  "timestamp": 1708312800
}
```

#### 2. Agent Card (A2A Discovery)

```
GET /.well-known/agent-card.json
```

**Response:**
```json
{
  "name": "BeeAI Predictive Maintenance Agent",
  "description": "AI-powered vehicle maintenance analysis",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "function_calling": false
  },
  "preferredTransport": "HTTP",
  "url": "http://localhost:8080"
}
```

#### 3. Chat Completions (Main Endpoint)

```
POST /chat/completions
```

**Headers:**
```
Content-Type: application/json
X-API-Key: beeai-maintenance-key-2024
```

**Request Body:**
```json
{
  "messages": [
    {
      "role": "user",
      "content": "Check maintenance for TRUCK-22"
    }
  ],
  "model": "watsonx:ibm/granite-4-h-small",
  "stream": true
}
```

**Response (SSE):**
```
data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":"..."}}]}
...
data: [DONE]
```
---

## 📞 Support & Resources

### Documentation

- **BeeAI Framework**: https://github.com/i-am-bee/bee-agent-framework
- **IBM watsonx**: https://www.ibm.com/docs/en/watsonx
- **watsonx Orchestrate**: https://www.ibm.com/docs/en/watsonx/watson-orchestrate
- **Langfuse**: https://langfuse.com/docs
- **Granite Models**: https://www.ibm.com/granite

---

## 👥 Authors

- **Ela Dixit**: ela.mishra@in.ibm.com  
- **Aakriti Aggarwal**: aakriti.aggarwal13@ibm.com  
- **Surya Deep Singh**: surya.deep.singh@ibm.com  

---

**Built for enterprise AI integration**

*Showcasing: BeeAI + watsonx + Granite + watsonx Orchestrate + Langfuse*