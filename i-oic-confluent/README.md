# Kafka MCP Server for watsonx Orchestrate

A production-ready MCP (Model Context Protocol) server that connects Kafka event streams to watsonx Orchestrate agents, deployed on IBM Code Engine.

## What This Does

Enables watsonx Orchestrate agents to consume and interact with Kafka events in real-time through cloud-deployed MCP tools.

## Directory Structure

```
confluent/
├── mcp_server_sse.py              # MCP server (SSE transport for cloud)
├── consumer.py                     # Kafka consumer implementation
├── requirements.txt                # Python dependencies
├── .env                           # Kafka credentials (not in git)
│
├── Dockerfile                      # Container definition
├── .dockerignore                  # Docker ignore patterns
├── deploy-to-code-engine.sh       # Automated deployment script
│
├── kafka-inventory-agent.yaml      # Agent configuration for watsonx
├── setup_and_test.sh              # Complete setup automation
├── produce_test_event.py          # Test event generator
│
└── venv/                          # Python virtual environment
```

## Quick Start

### 1. Set Up Kafka Credentials

Create a `.env` file with your Confluent Cloud credentials:

```bash
BOOTSTRAP_SERVER=pkc-xxx.us-east-2.aws.confluent.cloud:9092
API_KEY=your-api-key
API_SECRET=your-api-secret
```

### 2. Deploy to Code Engine

```bash
./deploy-to-code-engine.sh
```

This will:
- Build Docker image for linux/amd64
- Push to IBM Container Registry
- Deploy to Code Engine with Kafka credentials
- Provide the application URL

### 3. Register with watsonx Orchestrate

#### Option A: Automated Setup

```bash
source venv/bin/activate
orchestrate env activate <your-env-name>
./setup_and_test.sh
```

#### Option B: Manual Setup

```bash
# Register the MCP toolkit
orchestrate toolkits add \
  --kind mcp \
  --name kafka-consumer \
  --description "Kafka event consumer for inventory-events topic" \
  --url "https://kafka-mcp-server.XXXXX.us-south.codeengine.appdomain.cloud/sse" \
  --transport sse \
  --tools "*"

# Import the agent
orchestrate agents import --file kafka-inventory-agent.yaml
```

### 4. Test the Agent

#### Produce Test Events

```bash
source venv/bin/activate
python3 produce_test_event.py 10
```

This generates 10 test inventory events to Kafka.

#### Start Chat UI

```bash
orchestrate chat start
```

#### In the Web UI:

1. Select `kafka_inventory_agent` from the agent list
2. Go to the agent's Toolset tab
3. Click "Add tool" and select both tools from kafka-consumer toolkit:
   - `get_next_event`
   - `peek_queue_size`
4. Save the agent

#### Test Queries:

- "How many events are in the queue?"
- "Show me the next inventory event"
- "Get the latest 3 events"
- "What inventory changes happened recently?"

## Architecture

```
┌─────────────────────┐
│  Kafka Topic        │
│  inventory-events   │
└──────────┬──────────┘
           │
           │ (consume)
           ▼
┌─────────────────────┐
│  Code Engine        │
│  kafka-mcp-server   │
│                     │
│  ┌───────────────┐  │
│  │ Kafka Consumer│  │
│  │   (consumer.py)│  │
│  └───────┬───────┘  │
│          │          │
│          │ (queue)  │
│          ▼          │
│  ┌───────────────┐  │
│  │ MCP Server    │  │
│  │ (FastMCP/SSE) │  │
│  └───────────────┘  │
└──────────┬──────────┘
           │
           │ (HTTPS/SSE)
           ▼
┌─────────────────────┐
│  watsonx Orchestrate│
│                     │
│  ┌───────────────┐  │
│  │  kafka-consumer│  │
│  │   Toolkit     │  │
│  └───────┬───────┘  │
│          │          │
│          ▼          │
│  ┌───────────────┐  │
│  │ kafka_inventory│  │
│  │    _agent     │  │
│  └───────────────┘  │
└─────────────────────┘
```

## Available MCP Tools

### get_next_event

Retrieves the next Kafka event from the queue.

**Returns:**
```json
{
  "status": "event",
  "event": {
    "product_id": "WIDGET-001",
    "product_name": "Product WIDGET-001",
    "quantity": 100,
    "action": "restock",
    "timestamp": "2024-01-20T10:30:00Z",
    "warehouse": "WH-001"
  }
}
```

Or when queue is empty:
```json
{
  "status": "no_events"
}
```

### peek_queue_size

Returns the number of buffered events in memory.

**Returns:**
```json
{
  "size": 5
}
```

## Monitoring & Debugging

### Check Code Engine Status

```bash
ibmcloud ce app get -n kafka-mcp-server
```

### View Live Logs

```bash
ibmcloud ce app logs --name kafka-mcp-server --follow
```

### Test MCP Endpoint

```bash
curl -I https://kafka-mcp-server.XXXXX.us-south.codeengine.appdomain.cloud/sse
```

Expected response:
```
HTTP/2 200
content-type: text/event-stream; charset=utf-8
server: uvicorn
```

### List Registered Toolkits

```bash
orchestrate toolkits list | grep kafka-consumer
```

### List Deployed Agents

```bash
orchestrate agents list | grep kafka_inventory_agent
```

## Update Deployment

After code changes:

```bash
./deploy-to-code-engine.sh
```

Or manually:

```bash
# Build for linux/amd64
docker buildx build --platform linux/amd64 \
  -t "us.icr.io/NAMESPACE/kafka-mcp-server:latest" --push .

# Update Code Engine app
ibmcloud ce app update --name kafka-mcp-server \
  --image us.icr.io/NAMESPACE/kafka-mcp-server:latest
```

## Troubleshooting

### Issue: Toolkit registration fails

**Check MCP server is accessible:**
```bash
curl -I https://kafka-mcp-server.XXXXX.codeengine.appdomain.cloud/sse
```

**Verify Code Engine app is running:**
```bash
ibmcloud ce app get -n kafka-mcp-server
```

### Issue: Agent doesn't call tools

**Solution:** Manually add tools to the agent in the watsonx Orchestrate UI:
1. Open the agent editor
2. Go to "Toolset" tab
3. Click "Add tool"
4. Search for "kafka"
5. Select both `get_next_event` and `peek_queue_size`
6. Save the agent

**Verify toolkit is registered:**
```bash
orchestrate toolkits list | grep kafka-consumer -A 5
```

### Issue: No events returned

**Solution 1: Produce test events**
```bash
python3 produce_test_event.py 10
```

**Solution 2: Check Kafka connection**
```bash
ibmcloud ce app logs --name kafka-mcp-server --tail 50
```

Look for:
- "Kafka consumer started in background thread" (success)
- Kafka connection errors (check .env credentials)

### Issue: Container fails to start

**Check logs for error details:**
```bash
ibmcloud ce app logs --name kafka-mcp-server
ibmcloud ce app get -n kafka-mcp-server
ibmcloud ce app events -n kafka-mcp-server
```

**Common causes:**
- Missing or incorrect environment variables
- Kafka credentials expired or invalid
- Python dependency issues

### Issue: Tools not visible in UI

**Solution:** The YAML import doesn't automatically attach tools. You must manually add them:
1. Navigate to the agent in watsonx Orchestrate
2. Click on the agent name to edit
3. Go to "Toolset" section
4. Click "Add tool" button
5. Search for "kafka-consumer"
6. Select both tools (get_next_event, peek_queue_size)
7. Save changes

## Test Event Structure

The `produce_test_event.py` script generates events with this structure:

```json
{
  "event_id": "test-1703073600.123",
  "product_id": "WIDGET-001",
  "product_name": "Product WIDGET-001",
  "quantity": 100,
  "action": "restock",
  "timestamp": "2024-01-20T10:30:00Z",
  "warehouse": "WH-001"
}
```

Sample events include:
- WIDGET-001: restock 100 units
- GADGET-002: restock 50 units
- TOOL-003: sold 25 units
- PART-004: restock 200 units
- ITEM-005: returned 75 units

## Security

- Kafka credentials stored as Code Engine environment variables (encrypted at rest)
- HTTPS automatically enabled for Code Engine apps
- MCP server accessible only via public endpoint
- No authentication on MCP endpoints (add if needed for production)

## Cleanup

```bash
# Remove agent
orchestrate agents remove --name kafka_inventory_agent --kind native

# Remove toolkit
orchestrate toolkits remove --name kafka-consumer

# Delete Code Engine application
ibmcloud ce app delete --name kafka-mcp-server
```

## Key Files Reference

| File | Purpose |
|------|---------|
| `mcp_server_sse.py` | MCP server with SSE transport, exposes Kafka tools |
| `consumer.py` | Kafka consumer that buffers events in a thread-safe queue |
| `requirements.txt` | Python dependencies (fastmcp, confluent-kafka, etc.) |
| `Dockerfile` | Container definition for linux/amd64 deployment |
| `deploy-to-code-engine.sh` | Automated deployment script with error handling |
| `kafka-inventory-agent.yaml` | Agent configuration for watsonx Orchestrate |
| `setup_and_test.sh` | Automated toolkit registration and agent import |
| `produce_test_event.py` | Generate test Kafka events for validation |
| `.env` | Kafka credentials (not in version control) |

## Resources

- [MCP Protocol Specification](https://modelcontextprotocol.io)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [IBM Code Engine Docs](https://cloud.ibm.com/docs/codeengine)
- [watsonx Orchestrate Docs](https://www.ibm.com/docs/en/watsonx-orchestrate)
- [Confluent Kafka Python](https://docs.confluent.io/kafka-clients/python/current/overview.html)
