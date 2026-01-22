## 🔐 Post-Setup Configuration (Okta + MCP)

After setting up **Okta** and deploying the **MCP server**, you can run the full automation script.

Before running the automation, update the `config.env` file inside the automation script directory with the appropriate values.

### Required Environment Variables

```env
# MCP Server
MCP_SERVER_URL="https://mcp.example.com/mcp"

# Okta (ONLY base Okta URL, no -admin)
OKTA_BASE_URL="https://trial-1234567.okta.com"

# Okta OAuth Clients
API_SERVICES_CLIENT_ID="api_services_client_id_dummy"
API_SERVICES_CLIENT_SECRET="api_services_client_secret_dummy"
SPA_CLIENT_ID="spa_client_id_dummy"

# Watson Orchestrate
SERVICE_INSTANCE_URL="https://api.example.watson-orchestrate.cloud.ibm.com/instances/instance-id"
IAM_API_KEY="iam_api_key_dummy"
```

---

## 🧩 Next.js Environment Configuration

After running the `automate.sh` script, the `.env` file of the **Next.js application** will be automatically updated.

Alternatively, if you have already completed the entire setup flow, you can manually update the `.env` file with the required values.

### Required Next.js Environment Variables

```env
NEXT_PUBLIC_SPA_CLIENT_ID="spa_client_id_dummy"
NEXT_PUBLIC_OKTA_BASE_URL="https://trial-1234567.okta.com"

NEXT_PUBLIC_ORCHESTRATE_ORCHESTRATIONID="orchestration_id_dummy"
NEXT_PUBLIC_ORCHESTRATE_HOSTURL="https://region.watson-orchestrate.cloud.ibm.com"
NEXT_PUBLIC_ORCHESTRATE_CRN="crn:v1:bluemix:public:watsonx-orchestrate:region:a/account-id:instance-id::"

NEXT_PUBLIC_ORCHESTRATE_AGENT_ID="agent_id_dummy"
NEXT_PUBLIC_ORCHESTRATE_AGENT_ENVIRONMENT_ID="agent_environment_id_dummy"

NEXT_PUBLIC_CLIENT_PRIVATE_KEY="client_private_key_dummy"
NEXT_PUBLIC_CLIENT_PUBLIC_KEY="client_public_key_dummy"
NEXT_PUBLIC_IBM_PUBLIC_KEY="ibm_public_key_dummy"
```

---

# Project Setup Guide

## Setup Instructions

### 1. Navigate to the project folder

```
cd <path_to_ibm_code_folder>/obo_code
```

### 2. Install Dependencies

Run the following command to install all required dependencies:

```bash
npm install && npm install node-rsa
```

This will:

- Install project dependencies
- Install Playwright and NodeRSA
- Download required Playwright browser binaries

### 3. Run the Application

After the installation completes, start the development server:

```bash
npm run dev
```

The application should now be running successfully.
