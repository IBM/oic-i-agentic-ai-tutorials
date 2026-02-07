# Embed Chat WebApp -- Setup & Run Guide

## 📂 Folder Structure

### 1️⃣ [okta_setup](okta_setup/Okta_OAuth_2.0%E2%80%93On-Behalf-Of_%28OBO%29_Flow_Setup.md)

This folder contains the instructions to set up the identity provider (IdP) for this tutorial.

---

### 2️⃣ [mcp_server_code](mcp_server_code)

This folder contains the MCP server code and the instructions to deploy it on IBM Code Engine.

---

### 3️⃣ [hr_agent_automation](hr_agent_automation)

This folder contains all the code for agents, connections, and tools to be deployed in Orchestrate.

---

### 4️⃣ [enable_security_wxo](enable_security_wxo)

This folder contains the files needed to enable security for the watsonx Orchestrate chat.

---

### 5️⃣ [embed_chat_webapp](embed_chat_webapp)

This folder contains the web application code used to load the Orchestrate agent.


After setting up Okta using the [**setup guide**](okta_setup/Okta_OAuth_2.0%E2%80%93On-Behalf-Of_%28OBO%29_Flow_Setup.md), you will obtain the following values:

- `OKTA_BASE_URL`
- `SPA_CLIENT_ID`
- `API_SERVICES_CLIENT_ID`
- `API_SERVICES_CLIENT_SECRET`

## Update Okta Configuration

Before deploying the MCP server, update the **OKTA_BASE_URL** in `server.py` with the value obtained during the Okta setup, as shown below:

```python
OKTA_ISSUER = os.getenv(
    "OIDC_ISSUER",
    "<OKTA_BASE_URL>/oauth2/default"
)
```

## Deploy MCP Server

After updating the configuration, follow the [**steps**](mcp_server_code/code-engine-deployment-steps) to deploy the MCP server on **IBM Code Engine**.

Once the deployment is complete, you will obtain the following value:

- `MCP_SERVER_URL`

This URL is required for the web application to communicate with the MCP server.




Before running the web app, ensure the `.env` file is updated inside:

    embed_chat_webapp/.env



------------------------------------------------------------------------

## Option 1: Manual Configuration

Follow the documentation to  update the `.env` file.

    embed_chat_webapp/.env

Add the following:

``` env
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

------------------------------------------------------------------------

## Option 2: Run the Automation Script

The automation script will populate the `embed_chat_webapp/.env` file automatically.

### Step 1: Update Config File

Edit:

    hr_agent_automation/scripts/config.env

Add the following values:

``` env
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

### Step 2: Run Automation Script

``` bash
cd hr_agent_automation/scripts
./automate.sh
```

This script will:

-   Automatically generate the `.env` file and place it inside the `embed_chat_webapp` folder.




## ▶ Run the Web Application

Navigate to the web app directory:

``` bash
cd embed_chat_webapp
```

Install dependencies:

``` bash
npm install && npm install node-rsa
```

Start the app:

``` bash
npm run dev
```

 The Embed Chat WebApp should now be running successfully.

------------------------------------------------------------------------

##  Notes

-   Always use **base Okta URL** (no `-admin`)
-   Ensure MCP server is deployed before running automation
-   Automation script is the preferred approach to avoid manual mistakes

------------------------------------------------------------------------


