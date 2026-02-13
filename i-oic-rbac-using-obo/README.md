# Overview 
In this tutorial, you will learn how to implement context-aware RBAC for agentic AI using watsonx Orchestrate and On-Behalf-Of (OBO) authorization to secure tool and data access end-to-end.

# Technical SOlution 

## Secure Authentication & Authorization Flow

This section describes the end-to-end secure authentication and authorization flow used to establish a trusted chat session between a web client and an MCP server, mediated by **watsonx Orchestrate (WXO)** and **Watsonx Connection Manager (WCM)**.  
The accompanying sequence diagram illustrates this flow visually.

![Architecture Diagram](images/RBAC_Sequence.png)

---

## 1. Initial Key Setup

For any runtime communication, the web app generates an RSA key pair and shares its public key with watsonx Orchestrate, while obtaining the watsonx public key in return.  
This ensures secure payload exchange.

This is a **one-time setup** required to establish trust between the client and watsonx Orchestrate.

### Steps

1. On the client side, generate a **4096-bit RSA key pair**:
   - `client_private_key`
   - `client_public_key`

2. From watsonx Orchestrate, retrieve the **wxo_public_key (IBM public key)**:
   - Shared with the client
   - Used by the client to encrypt sensitive user payload data
   - Orchestrate decrypts using its corresponding `wxo_private_key`

3. The client shares the **client_public_key** with watsonx Orchestrate:
   - Used later by Orchestrate to verify JWTs signed with `client_private_key`

---

## 2. User Authentication via Web Client

When a user logs in to the web app, authentication is delegated to the enterprise **Identity Provider (IdP)** (Okta in this case).

### Flow

1. User logs in through the web client.
2. Web client authenticates the user with the IdP.
3. Upon successful authentication, the IdP returns standard OAuth tokens:
   - `access_token`
   - `id_token`

---

## 3. Secure Payload Preparation on the Web Client

1. The web client constructs a `user_payload` object containing:
   - `sso_token` → the `access_token`
   - Optional additional user attributes

2. The `user_payload` is **encrypted using the `wxo_public_key`** to ensure confidentiality.

3. The `id_token` is decoded on the client side:
   - Contains user identity and profile information
   - Selected fields are extracted and passed as **context**

---

## 4. JWT Construction on the Client

The web client constructs a **signed JWT** to initiate the secure chat.

### Process

1. JWT is signed using the `client_private_key` (**RS256**).
2. The signed JWT is sent to watsonx Orchestrate.

### JWT Claims Included

- **sub (Subject)** → Authenticated user identifier  
- **iat (Issued At)** → Token creation timestamp  
- **exp (Expiration Time)** → Token expiry timestamp  
- **user_payload** → Encrypted payload containing the SSO access token  
- **context** → User context derived from the decoded `id_token`

---

## 5. Token Validation & Extraction in watsonx Orchestrate (WXO)

Upon receiving the JWT:

1. Verify the JWT signature using the `client_public_key`.
2. Decode the JWT to extract:
   - Encrypted `user_payload`
   - Context information
3. Decrypt the `user_payload` using the `wxo_private_key`.
4. Extract the `access_token` from the `sso_token`.
5. Forward the `access_token` to **WCM**.

---

## 6. OAuth 2.0 On-Behalf-Of (OBO) Flow via WCM

1. WCM performs an **OAuth 2.0 OBO token exchange** with the IdP.
2. The original user `access_token` is exchanged for:
   - `refreshed_access_token`
   - Properly scoped for downstream MCP access

---

## 7. MCP Server Authorization

1. WCM passes the `refreshed_access_token` to the MCP Server.
2. MCP server authorizes itself with the IdP.
3. IdP validates the token and establishes a trusted connection.
4. MCP server confirms:
   - Authorization successful
   - MCP tools are available
5. MCP notifies watsonx Orchestrate that the tools are ready.

---

## 8. Secure Chat Session Established

Once authorization succeeds:

1. A secure chat session is established with watsonx Orchestrate.
2. The agent can invoke MCP tools within the user’s permission boundaries.
3. The agent acts **on behalf of the user** using delegated authorization.
4. Every action is **traceable to the authenticated user identity**.

---


# Code Setup

## 📂 Folder Structure

### [okta_setup](okta_setup/Okta_OAuth_2.0%E2%80%93On-Behalf-Of_%28OBO%29_Flow_Setup.md)

This folder contains the instructions to set up the Okta identity provider (IdP) for this tutorial.

---

### [mcp_server_code](mcp_server_code)

This folder contains the MCP server code and the instructions to deploy it on IBM Code Engine.

---

### [hr_agent_automation](hr_agent_automation)

This folder contains all the code for agents, connections, and tools to be deployed in Orchestrate.

---

### [enable_security_wxo](enable_security_wxo)

This folder contains the files needed to enable security for the watsonx Orchestrate chat.

---

### [embed_chat_webapp](embed_chat_webapp)

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


