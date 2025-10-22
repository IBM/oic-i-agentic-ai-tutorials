# HR Agent - Employee Onboarding for Watsonx Orchestrate

A simple HR agent that processes employee onboarding requests from natural language. Built to integrate seamlessly with Watsonx Orchestrate and other orchestration platforms.

## What It Does

The HR agent accepts natural language requests like:
- "Onboard Sarah Williams as a Software Engineer"
- "Onboard John Smith as Senior Data Analyst"
- "Onboard Maria Garcia as Product Manager"

And generates structured employee records with:
- Auto-generated employee ID (e.g., E-47025)
- Derived email address (e.g., sarah.williams@example.com)
- Job title and full name

## Features

- **Natural Language Processing**: Simple regex-based parsing that handles common variations
- **OpenAI-Compatible API**: Standard `/v1/chat/completions` endpoint for broad compatibility
- **A2A Agent Card**: Discovery endpoint at `/.well-known/agent-card.json`
- **SSE Streaming**: Real-time response streaming for better user experience
- **Dual Format Response**: Both human-readable text and machine-parseable JSON
- **Cloud Ready**: Containerized and optimized for IBM Code Engine deployment

## Architecture

This agent uses a **hybrid approach** that combines OpenAI-style APIs with A2A discovery:

```
hr-agent/
├── __init__.py           # Package initialization with version info
├── main.py              # HTTP server with all API endpoints
├── agent_executor.py    # Core onboarding business logic
├── requirements.txt     # Minimal dependencies (Starlette + Uvicorn)
├── Dockerfile          # Multi-stage container build
├── deploy.sh           # IBM Code Engine deployment automation
└── hr_agent.yaml       # Watsonx Orchestrate import configuration
```

### Why This Approach?

Rather than using the full A2A SDK, we built a lightweight implementation that:
- Works with Watsonx Orchestrate's A2A 0.2.1 support
- Has minimal dependencies for faster startup
- Provides broader compatibility through OpenAI format
- Is easier to understand and customize

## Local Development & Testing

### Prerequisites

- Python 3.10 or higher
- pip or uv package manager

### Installation

1. **Install dependencies:**

```bash
cd a2a/hr-agent
pip install -r requirements.txt
```

2. **Run the agent locally:**

```bash
python main.py

# Or set custom port
PORT=9000 python main.py
```

The agent will start on `http://localhost:8080` (or the PORT you specify).

### Test Locally

**1. Check the Agent Card (A2A Discovery)**

```bash
curl http://localhost:8080/.well-known/agent-card.json | jq .
```

Expected response:
```json
{
  "spec_version": "v1",
  "kind": "external",
  "name": "HR Agent",
  "description": "HR agent that creates employee records from natural language",
  "url": "http://localhost:8000/",
  "version": "1.0.0",
  "default_input_modes": ["text"],
  "default_output_modes": ["text"],
  "capabilities": {
    "streaming": true
  },
  "skills": [
    {
      "id": "employee_onboarding",
      "name": "Employee Onboarding",
      "description": "Creates employee records from natural language onboarding requests",
      "tags": ["hr", "onboarding", "employee"],
      "examples": [
        "Onboard Sarah Williams as a Software Engineer",
        "Onboard John Smith as Senior Data Analyst",
        "Onboard Maria Garcia as Product Manager"
      ]
    }
  ]
}
```

**2. Test Employee Onboarding (OpenAI Chat Completions)**

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "Onboard Sarah Williams as a Software Engineer"
      }
    ]
  }'
```

Expected response (streaming):
```
Employee onboarded successfully

• Employee ID: E-12345
• Full Name: Sarah Williams
• Email: sarah.williams@example.com
• Job Title: Software Engineer

BEGIN_IT_JSON
{"employeeId":"E-12345","fullName":"Sarah Williams","email":"sarah.williams@example.com","jobTitle":"Software Engineer"}
END_IT_JSON
```

**3. Test with Python Client**

```python
import httpx
import json

# Test agent card
response = httpx.get("http://localhost:8080/.well-known/agent-card.json")
print("Agent Card:", json.dumps(response.json(), indent=2))

# Test onboarding with streaming
with httpx.stream(
    "POST",
    "http://localhost:8080/v1/chat/completions",
    json={
        "messages": [
            {
                "role": "user",
                "content": "Onboard Sarah Williams as a Software Engineer"
            }
        ]
    },
    headers={"Content-Type": "application/json"},
    timeout=30.0
) as response:
    for line in response.iter_lines():
        if line.startswith("data: "):
            data = line[6:]  # Remove "data: " prefix
            if data != "[DONE]":
                event_data = json.loads(data)
                content = event_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if content:
                    print(content, end="", flush=True)
    print()  # New line at end
```

## Deployment to IBM Cloud Code Engine

### Prerequisites

- IBM Cloud account with Code Engine access
- IBM Cloud CLI installed (`ibmcloud`)
- Code Engine plugin installed (`ibmcloud plugin install code-engine`)
- Docker with buildx support
- Logged in to IBM Cloud (`ibmcloud login --sso`)

### Update Configuration

Edit [deploy.sh](deploy.sh) and update these values:

```bash
RESOURCE_GROUP="your-resource-group"
PROJECT_NAME="your-code-engine-project"
REGISTRY="us.icr.io"
REGISTRY_NAMESPACE="your-registry-namespace"
HR_URL="https://your-app-url.codeengine.appdomain.cloud"
```

### Deploy

```bash
# Make the script executable
chmod +x deploy.sh

# Run deployment
./deploy.sh
```

The script will:
1. Build the Docker image for linux/amd64 platform
2. Push to IBM Container Registry
3. Create/update the Code Engine application
4. Test the deployment
5. Display the agent card and test an onboarding request

### After Deployment

Your agent will be available at the URL shown in the deployment output. The agent card will be accessible at:

```
https://your-app-url/.well-known/agent-card.json
```

## Integration with Watsonx Orchestrate

### Add the Agent to Watsonx Orchestrate

1. **Update the [hr_agent.yaml](hr_agent.yaml) file:**

Replace the `api_url` with your deployed Code Engine URL:

```yaml
api_url: "https://your-app-url.codeengine.appdomain.cloud"
```

2. **Import into Watsonx Orchestrate:**

- Log in to your Watsonx Orchestrate instance
- Navigate to **Agent Builder** or **Skills**
- Click **Add External Agent**
- Upload or paste the contents of `hr_agent.yaml`
- The agent will be available for use in conversation flows

3. **Test in Orchestrate:**

Try these commands in the Watsonx Orchestrate chat:
- "Onboard Sarah Williams as a Software Engineer"
- "Onboard John Smith as Senior Data Analyst"
- "Onboard Maria Garcia as Product Manager"

### Multi-Agent Workflows

The HR agent outputs structured JSON (between `BEGIN_IT_JSON` and `END_IT_JSON` markers) that can be consumed by downstream agents (e.g., an IT provisioning agent) to create complete onboarding workflows.

## Implementation Details

### Hybrid Approach

This agent uses a hybrid architecture that combines:

1. **OpenAI-Compatible Endpoint** (`/v1/chat/completions`):
   - Standard format recognized by many tools
   - Simple request/response structure
   - SSE streaming support

2. **A2A Agent Card** (`/.well-known/agent-card.json`):
   - Advertises A2A 0.2.1 compatibility
   - Lists available skills and capabilities
   - Enables discovery by orchestration platforms

### Why Not Pure A2A SDK?

While the A2A SDK provides a complete implementation:
- Watsonx Orchestrate currently supports A2A 0.2.1
- The A2A Python SDK (0.3.x) implements protocol 0.3.0+
- Our hybrid approach avoids version conflicts
- Lighter dependencies mean faster cold starts
- OpenAI format provides broader tool compatibility

### Response Format

The agent returns responses in a dual format:

```
[Human-Readable Text]
Employee onboarded successfully
• Employee ID: E-47180
• Full Name: Test User
• Email: test.user@example.com
• Job Title: QA Engineer

[Machine-Parseable JSON]
BEGIN_IT_JSON
{"employeeId":"E-47180","fullName":"Test User","email":"test.user@example.com","jobTitle":"QA Engineer"}
END_IT_JSON
```

This enables both user-facing display and downstream automation.

## Troubleshooting

### Agent won't start locally

- Check Python version: `python --version` (must be 3.10+)
- Verify dependencies: `pip install -r requirements.txt`
- Check port availability: `lsof -i :8080`
- Try running with verbose logging: `python main.py`

### Deployment fails

- Verify IBM Cloud login: `ibmcloud target`
- Check Docker is running: `docker ps`
- Verify buildx is available: `docker buildx version`
- Check registry credentials: `ibmcloud cr login`

### Agent not responding in Orchestrate

- Verify agent card URL is accessible: `curl https://your-url/.well-known/agent-card.json`
- Check the `api_url` in `hr_agent.yaml` matches your deployment
- Test the chat endpoint directly: `curl -X POST https://your-url/v1/chat/completions ...`
- Check Code Engine logs: `ibmcloud ce app logs --name hr-agent-a2a`
- Verify the agent is running: `ibmcloud ce app get --name hr-agent-a2a`

## Development

To modify the agent:

1. **Update business logic**: Edit [agent_executor.py](agent_executor.py) - this contains the core onboarding logic
2. **Modify server/API**: Edit [main.py](main.py) - this handles HTTP requests and streaming
3. **Test locally**: Run `python main.py` and test with curl
4. **Deploy changes**: Run `./deploy.sh` to build and deploy to Code Engine
5. **Update Orchestrate config**: If you change endpoints or skills, update [hr_agent.yaml](hr_agent.yaml)

## License

See repository license.

## Resources

- [A2A Protocol Documentation](https://a2a-protocol.org/)
- [A2A Python SDK](https://github.com/a2a-protocol/a2a-sdk-python)
- [IBM Cloud Code Engine Documentation](https://cloud.ibm.com/docs/codeengine)
- [Watsonx Orchestrate Documentation](https://www.ibm.com/docs/en/watsonx/watson-orchestrate)
