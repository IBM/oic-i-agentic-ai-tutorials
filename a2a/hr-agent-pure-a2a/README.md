# HR Agent - Pure A2A Protocol

A pure Agent-to-Agent (A2A) protocol implementation for watsonx Orchestrate. Creates employee records from natural language requests using JSON-RPC 2.0.

### Project Structure

```
hr-agent-pure-a2a/
├── app/
│   ├── __init__.py           # Package initialization
│   ├── __main__.py           # Server setup and configuration
│   ├── agent.py              # HR agent business logic
│   └── agent_executor.py     # A2A protocol executor
├── deploy.sh                 # Deployment automation script
├── test_agent.sh             # Automated test suite
├── verify_a2a.sh             # A2A protocol verification
├── hr_agent.yaml             # Watsonx Orchestrate import config
├── hr_manager_agent.yaml     # Optional manager agent config
├── Dockerfile                # Container image definition
├── requirements.txt          # Python dependencies
├── pyproject.toml            # Project metadata
└── README.md                 # This file
```

### Component Interaction

```
User Request
    |
    v
Watsonx Orchestrate
    |
    v
A2A JSON-RPC Message
    |
    v
A2AStarletteApplication (a2a-sdk)
    |
    v
DefaultRequestHandler
    |
    v
HRAgentExecutor
    |
    v
HRAgent (business logic)
    |
    v
Response with artifacts
    |
    v
Back to Watsonx Orchestrate
```

### Key Components

#### 1. HRAgent (`app/agent.py`)

Core business logic for processing employee onboarding requests.

**Responsibilities:**

- Parse natural language requests
- Generate employee IDs and emails
- Create structured employee records
- Stream status updates

#### 2. HRAgentExecutor (`app/agent_executor.py`)

A2A protocol executor implementing the AgentExecutor interface.

**Responsibilities:**

- Manage task lifecycle
- Handle task state transitions
- Stream updates to clients
- Add artifacts to completed tasks

#### 3. Server (`app/__main__.py`)

Server initialization and configuration.

**Responsibilities:**

- Set up A2A application
- Configure agent card
- Initialize request handlers
- Start HTTP server

## Quick Start

```bash
# 1. Deploy to IBM Code Engine
./deploy.sh

# 2. Import to Watsonx Orchestrate
orchestrate agents import -f hr_agent.yaml

# 3. Test in Orchestrate chat
# "Onboard John Doe as Software Engineer"
```

## Status

- **Protocol**: A2A JSON-RPC 2.0

## Prerequisites

**Required:**

- Python 3.12+
- Docker
- IBM Cloud CLI with Code Engine plugin
- Watsonx Orchestrate CLI

**Setup:**

```bash
# IBM Cloud login
ibmcloud login --sso
ibmcloud target -g <resource-group>
ibmcloud ce project select -n <project-name>

# Orchestrate CLI
pip install watsonx-orchestrate-cli
orchestrate env add -n my-env -u https://your-wxo-instance-url
orchestrate env activate my-env
```

## Deploy

### Automated Deployment

```bash
./deploy.sh
```

This builds, pushes, and deploys the agent to IBM Code Engine.

### Manual Deployment

```bash
# Build and push
docker buildx build --platform linux/amd64 -f Dockerfile \
  -t us.icr.io/<namespace>/hr-agent-pure-a2a:latest --push .

# Deploy
ibmcloud ce application create \
  --name hr-agent-pure-a2a \
  --image us.icr.io/<namespace>/hr-agent-pure-a2a:latest \
  --registry-secret icr-secret \
  --port 8080 \
  --cpu 0.5 \
  --memory 1G \
  --min-scale 1 \
  --max-scale 2
```

## Import to Watsonx Orchestrate

### Import HR Agent

```bash
orchestrate agents import -f hr_agent.yaml
```

Expected output:

```
[INFO] - External Agent 'hr_agent_pure_a2a' imported successfully
```

### Verify Import

```bash
orchestrate agents list
orchestrate agents get -n hr_agent_pure_a2a
```

### Import HR Manager Agent

The manager agent delegates onboarding tasks to the HR agent and handles broader HR questions:

```bash
orchestrate agents import -f hr_manager_agent.yaml
orchestrate agents get -n hr_manager_agent_pure_a2a
```

**Manager capabilities:**

- Delegates onboarding to hr_agent_pure_a2a
- Explains onboarding process
- Answers HR policy questions
- Clarifies job requirements

## Test

### Automated Tests

```bash
# Run all 10 tests
./test_agent.sh

# Verify A2A protocol
./verify_a2a.sh
```

### Test in Orchestrate Chat

**HR Agent:**

```
Onboard Sarah Williams as Software Engineer
```

**HR Manager Agent:**

```
I need to onboard a new employee named Jane Smith as Data Analyst
```

### Test with Curl

**Get agent card:**

```bash
curl https://hr-agent-pure-a2a.20xtogjmfdje.us-south.codeengine.appdomain.cloud/.well-known/agent.json | jq .
```

**Send A2A message:**

```bash
curl -X POST https://hr-agent-pure-a2a.20xtogjmfdje.us-south.codeengine.appdomain.cloud/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "test-001",
        "role": "user",
        "parts": [{"text": "Onboard Bob Wilson as DevOps Engineer"}]
      }
    },
    "id": 1
  }' | jq -r '.result.artifacts[0].parts[0].text'
```

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python -m app --host 0.0.0.0 --port 8080
```

**Local endpoints:**

- Agent Card: http://localhost:8080/.well-known/agent.json
- A2A Endpoint: http://localhost:8080/
- Health Check: http://localhost:8080/health

## Architecture

```
app/
├── __init__.py           # Package initialization
├── __main__.py           # Server setup (A2A application)
├── agent.py              # Business logic (employee onboarding)
└── agent_executor.py     # A2A protocol executor
```

**Flow:**

1. User request → Watsonx Orchestrate
2. A2A JSON-RPC message → Agent endpoint `/`
3. A2AStarletteApplication → DefaultRequestHandler
4. HRAgentExecutor → HRAgent (business logic)
5. Response with artifacts → Orchestrate

## A2A Protocol

**Endpoint:** `/` (root path)

**Request:**

```json
{
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "message": {
      "messageId": "unique-id",
      "role": "user",
      "parts": [{ "text": "Onboard John Doe as Software Engineer" }]
    }
  },
  "id": 1
}
```

**Response:**

```json
{
  "id": 1,
  "jsonrpc": "2.0",
  "result": {
    "id": "task-id",
    "status": { "state": "completed" },
    "artifacts": [
      {
        "parts": [
          {
            "text": "Employee onboarded successfully!\n\nEmployee ID: E-12345\n..."
          }
        ]
      }
    ]
  }
}
```

## Troubleshooting

**Agent not responding:**

```bash
ibmcloud ce app get --name hr-agent-pure-a2a
ibmcloud ce app logs --name hr-agent-pure-a2a --tail 100
```

**Import failed:**

```bash
curl https://hr-agent-pure-a2a.20xtogjmfdje.us-south.codeengine.appdomain.cloud/.well-known/agent.json
orchestrate env list
```

**Redeploy:**

```bash
./deploy.sh
```

### Import to Watsonx Orchestrate

```bash
# Import HR Agent
orchestrate agents import -f hr_agent.yaml

# Import HR Manager Agent
orchestrate agents import -f hr_manager_agent.yaml

# Deploy HR Manager Agent
orchestrate agents deploy -n hr_agent_pure_a2a
```
