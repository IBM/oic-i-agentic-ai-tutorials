# Embed Chat WebApp -- Setup & Run Guide

## 📂 Folder Structure

### 1️⃣ [okta_setup](okta_setup/Okta_OAuth_2.0%E2%80%93On-Behalf-Of_%28OBO%29_Flow_Setup.md)

Provides a detailed guide for setting up Okta, which is required for authentication in other components.

---

### 2️⃣ [mcp_server_code](mcp_server_code)

Contains the code to deploy the MCP server along with the deployment steps.


---

### 3️⃣ [hr_agent_automation](hr_agent_automation)

This folder contains the complete code for agents, connections and tools, you will deploy them in orchestrate.

---

### 4️⃣ [enable_security_wxo](enable_security_wxo)

Contains the script to enable security in the Watsonx Orchestrate instance.

---

### 5️⃣ [embed_chat_webapp](embed_chat_webapp)

This folder contains the code for the web application used to load the Orchestrate agent.

After setting up [**Okta**](okta_setup/Okta_OAuth_2.0%E2%80%93On-Behalf-Of_%28OBO%29_Flow_Setup.md) and deploying the [**MCP Server**](mcp_server_code), you can run
the full automation script or configure the web application manually.

There are **two ways** to run the `embed_chat_webapp`.

Before running the web app, ensure the `.env` file is updated inside:

    embed_chat_webapp/.env



------------------------------------------------------------------------

## Option 1: Manual Configuration

If you prefer not to run the automation script, you can manually update the configuration by following the documentation.

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

The automation script will populate the `.env` file automatically.

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


