# MCP Server Import into watsonx Orchestrate – Step-by-Step (Sample + Example)

This document shows **each step in two parts**:

1. **Sample (template)** – with placeholders
2. **Example** – with real values

This format is intended for **easy understanding and copy-paste usage**.

---

## Step 1: Get Bearer Token from Okta (Client Credentials)

### Sample

```bash
curl -X POST "<OKTA_BASE_URL>/oauth2/default/v1/token" \
  -H "Accept: application/json" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=client_credentials" \
  --data-urlencode "client_id=<API_SERVICES_CLIENT_ID>" \
  --data-urlencode "client_secret=<API_SERVICES_CLIENT_SECRET>" \
  --data-urlencode "scope=mcp.read"
```

### Example

```bash
curl -X POST "https://trial-5337334.okta.com/oauth2/default/v1/token" \
  -H "Accept: application/json" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=client_credentials" \
  --data-urlencode "client_id=0oay6gzw6zJq2LsUj697" \
  --data-urlencode "client_secret=********" \
  --data-urlencode "scope=mcp.read"
```

### Sample Response

```json
{
  "token_type": "Bearer",
  "access_token": "<ACCESS_TOKEN>",
  "expires_in": 300,
  "scope": "mcp.read"
}
```

---

## Step 2: Create Connection in Orchestrate

### Sample

```bash
orchestrate connections add -a <CONNECTION_NAME>
```

### Example

```bash
orchestrate connections add -a mcp_connection
```

---

## Step 3: Configure Connection with Bearer Auth (Draft)

### Sample

```bash
orchestrate connections configure \
  -a <CONNECTION_NAME> \
  --env draft \
  --type team \
  --kind bearer
```

### Example

```bash
orchestrate connections configure \
  -a mcp_connection \
  --env draft \
  --type team \
  --kind bearer
```

---

## Step 4: Set Bearer Token Credentials (For Import)

### Sample

```bash
orchestrate connections set-credentials \
  -a <CONNECTION_NAME> \
  --env draft \
  --token <ACCESS_TOKEN>
```

### Example

```bash
orchestrate connections set-credentials \
  -a mcp_connection \
  --env draft \
  --token eyJraWQiOiJxcmVUV0pLbGMt...
```

> This bearer token is required **only to import the MCP toolkit**.

---

## Step 5: Import MCP Toolkit

### Sample

```bash
orchestrate toolkits add \
  --kind mcp \
  --name <MCP_TOOLKIT_NAME> \
  --description "<MCP_TOOLKIT_DESCRIPTION>" \
  --url <MCP_TOOLKIT_URL> \
  --transport streamable_http \
  --tools "*" \
  --app-id <CONNECTION_NAME>
```

### Example

```bash
orchestrate toolkits add \
  --kind mcp \
  --name mcp_toolkit \
  --description "My MCP toolkit" \
  --url "mcp_server_url" \
  --transport streamable_http \
  --tools "*" \
  --app-id mcp_connection
```

---

## Step 6: Switch Connection to OBO Flow

### Sample connection.yaml

```yaml
app_id: <CONNECTION_NAME>
spec_version: v1
kind: connection

environments:
  draft:
    sso: true
    server_url: <TOKEN_URL>
    kind: oauth_auth_token_exchange_flow
    type: member
    app_config:
      header:
        content-type: application/x-www-form-urlencoded

  live:
    sso: true
    server_url: <TOKEN_URL>
    kind: oauth_auth_token_exchange_flow
    type: member
    app_config:
      header:
        content-type: application/x-www-form-urlencoded
```

### Example connection.yaml

```yaml
app_id: mcp_connection
spec_version: v1
kind: connection

environments:
  draft:
    sso: true
    server_url: https://trial-5337334.okta.com/oauth2/default/v1/token
    kind: oauth_auth_token_exchange_flow
    type: member
    app_config:
      header:
        content-type: application/x-www-form-urlencoded

  live:
    sso: true
    server_url: https://trial-5337334.okta.com/oauth2/default/v1/token
    kind: oauth_auth_token_exchange_flow
    type: member
    app_config:
      header:
        content-type: application/x-www-form-urlencoded
```

Import the connection:

```bash
orchestrate connections import -f connection.yaml
```

---

## Step 7: Configure OBO Token Exchange Credentials

### Sample

```bash
orchestrate connections set-credentials \
  --app-id <CONNECTION_NAME> \
  --env live \
  --client-id <API_SERVICES_CLIENT_ID> \
  --grant-type urn:ietf:params:oauth:grant-type:token-exchange \
  --token-url <TOKEN_URL> \
  -t "body:client_secret=<API_SERVICES_CLIENT_SECRET>" \
  -t "body:subject_token_type=urn:ietf:params:oauth:token-type:access_token" \
  -t "body:scope=mcp.read" \
  -t "body:audience=api://default" \
  -t "body:app_token_key=subject_token"
```

### Example

```bash
orchestrate connections set-credentials \
  --app-id mcp_connection \
  --env live \
  --client-id 0oay6gzw6zJq2LsUj697 \
  --grant-type urn:ietf:params:oauth:grant-type:token-exchange \
  --token-url https://trial-5337334.okta.com/oauth2/default/v1/token \
  -t "body:client_secret=********" \
  -t "body:subject_token_type=urn:ietf:params:oauth:token-type:access_token" \
  -t "body:scope=mcp.read" \
  -t "body:audience=api://default" \
  -t "body:app_token_key=subject_token"
```

---
