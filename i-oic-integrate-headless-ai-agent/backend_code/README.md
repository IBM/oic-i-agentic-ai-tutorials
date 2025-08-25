# Integrate watsonx Orchestrate AI Agents in Custom UI - Backend Components

## Back End Instructions

### Disclaimer
- This is PoC quality code not meant to be deployed as-is in Production.
- Clearly, it can be improved.

### Prerequisites
- Note that the CrewAI version used requires Python >= v3.10 and < v3.13.
- Install [Podman](https://podman.io) to be able to manage containers.
- Install [uv package manager](https://docs.astral.sh/uv/getting-started/installation/) **(DO NOT USE PIP)**.

---

## Installing Application in IBM Code Engine
**Note:** Same steps are also documented in `deployment-guide.md` for quick reference.

### 1. Login to IBM Cloud
```bash
colima start
ibmcloud login --sso
```

### 2. List All Resource Groups
```bash
ibmcloud resource groups
```

### 3. Select the Resource Group
```bash
ibmcloud target -g showcase-ai-assistants
```

### 4. Create a Project in IBM Cloud
Create a project in the IBM Cloud UI and name it `ce-riskbud-mcp`. Then run:
```bash
ibmcloud ce project select -n ce-riskbud-mcp
```

### 5. Generate the Image and Push to Registry
```bash
ibmcloud cr login
brew install docker-buildx

docker buildx build --platform linux/amd64 --push -t us.icr.io/itz-watson-apps-9vhke6kc-cr/agent_integration_tutorial:latest .
```

### 6. Create the Secret
```bash
ibmcloud ce registry create \
  --name icr-tutorial-secret \
  --server us.icr.io \
  --username iamapikey \
  --password REPLACE_WITH_APIKEY
```

### 7. Create the Application via IBM Code Engine UI
**Note:** Manual creation via CLI may fail due to permission issues.

If you get an error while deploying the application, run the following update and deploy command:
```bash
ibmcloud ce application update \
  --name ce-agent-integration-in-customui \
  --image us.icr.io/itz-watson-apps-9vhke6kc-cr/agent_integration_tutorial:latest \
  --registry-secret icr-tutorial-secret \
  --port 8000
```

### 8. Test the Application
```bash
curl -X GET "YOUR_APPLICATION_CODE_ENGINE_URL/chat/v2?query=show%20me%20duplicate%20invoices%20&agent_id=87e081f7-4fdb-42e4-9ddd-16bb3ce4d8fc&include_raw=0" -H "accept: application/json"
```

**Note:** The URL for the deployed application will be unique, copy it from the IBM Code Engine UI