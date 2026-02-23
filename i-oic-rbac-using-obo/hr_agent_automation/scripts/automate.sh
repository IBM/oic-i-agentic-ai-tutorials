#!/usr/bin/env bash
set -euo pipefail


ORCHESTRATE_CMD="orchestrate"
MCP_TOOLKIT_DESCRIPTION="My MCP toolkit"
NAME_OF_INSTANCE="saas"
ORCHESTRATE_CONNECTION_APP_NAME="mcp_connection"
ORCHESTRATE_MCP_TOOLKIT_NAME="mcp_tools_server"
SCOPE="mcp.read"
AUDIENCE="api://default"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_OUTPUT_FILE="${SCRIPT_DIR}/../../embed_chat_webapp/.env"

# =========================================================
# Clear .env at start
# =========================================================
mkdir -p "$(dirname "$ENV_OUTPUT_FILE")"
: > "$ENV_OUTPUT_FILE"


# =========================================================
# Keys directory
# =========================================================
KEYS_DIR="${SCRIPT_DIR}/keys"
mkdir -p "$KEYS_DIR"

CLIENT_PUBLIC_KEY_FILE="${KEYS_DIR}/client_public_key.pem"
CLIENT_PRIVATE_KEY_FILE="${KEYS_DIR}/client_private_key.pem"
IBM_PUBLIC_KEY_FILE="${KEYS_DIR}/ibm_public_key.pem"

# =========================================================
# Helper: write env var
# =========================================================
write_env_var() {
  local key="$1" value="$2" file="$3"
  mkdir -p "$(dirname "$file")"
  touch "$file"

  local escaped
  escaped=$(printf '%s\n' "$value" | sed 's/[\/&]/\\&/g')

  if grep -qE "^${key}[[:space:]]*=" "$file"; then
    sed -i "" "s|^${key}[[:space:]]*=.*|${key} = ${escaped}|" "$file"
  else
    echo "${key} = ${value}" >> "$file"
  fi
}

# =========================================================
# Helper: read multiline input (ENTER twice)
# =========================================================
read_multiline_input() {
  local line content=""
  while IFS= read -r line; do
    [[ -z "$line" ]] && break
    content+="${line}"$'\n'
  done
  printf "%s" "$content"
}

# =========================================================
# Load config
# =========================================================
CONFIG_FILE="${1:-${SCRIPT_DIR}/config.env}"
[[ -f "$CONFIG_FILE" ]] || { echo "❌ Config file not found"; exit 1; }
# shellcheck source=/dev/null
. "$CONFIG_FILE"


: "${MCP_SERVER_URL:?missing MCP_SERVER_URL}"
: "${OKTA_BASE_URL:?missing OKTA_BASE_URL}"
: "${API_SERVICES_CLIENT_ID:?missing API_SERVICES_CLIENT_ID}"
: "${API_SERVICES_CLIENT_SECRET:?missing API_SERVICES_CLIENT_SECRET}"
: "${SPA_CLIENT_ID:?missing SPA_CLIENT_ID}"
: "${SERVICE_INSTANCE_URL:?missing SERVICE_INSTANCE_URL}"
: "${IAM_API_KEY:?missing IAM_API_KEY}"

OKTA_TOKEN_URL="${OKTA_BASE_URL}/oauth2/default/v1/token"

command -v curl >/dev/null || exit 2
command -v jq >/dev/null || exit 3
command -v openssl >/dev/null || exit 4
command -v awk >/dev/null || exit 5

# =========================================================
# Secure Embed pre-check
# =========================================================
echo "🔐 Is Secure Embed already enabled in this instance? (Do you already have client_public_key, client_private_key, and ibm_public_key?)"
read -r -p "Enter yes or no: " SECURE_EMBED_ENABLED
SECURE_EMBED_ENABLED=$(echo "$SECURE_EMBED_ENABLED" | tr '[:upper:]' '[:lower:]')

if [[ "$SECURE_EMBED_ENABLED" == "yes" ]]; then
  echo "📌 Paste CLIENT PUBLIC KEY in multiline format (do not paste the flattened key), then press ENTER twice:"
  CLIENT_PUBLIC_KEY_RAW=$(read_multiline_input)

  echo "📌 Paste CLIENT PRIVATE KEY in multiline format (do not paste the flattened key), then press ENTER twice:"
  CLIENT_PRIVATE_KEY_RAW=$(read_multiline_input)

  echo "📌 Paste IBM PUBLIC KEY in multiline format (do not paste the flattened key), then press ENTER twice:"
  IBM_PUBLIC_KEY_RAW=$(read_multiline_input)

  printf "%s\n" "$CLIENT_PUBLIC_KEY_RAW"  > "$CLIENT_PUBLIC_KEY_FILE"
  printf "%s\n" "$CLIENT_PRIVATE_KEY_RAW" > "$CLIENT_PRIVATE_KEY_FILE"
  printf "%s\n" "$IBM_PUBLIC_KEY_RAW"     > "$IBM_PUBLIC_KEY_FILE"
else
  echo "🔐 Generating client RSA keys..."
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 \
    -out "$CLIENT_PRIVATE_KEY_FILE" 2>/dev/null

  openssl pkey -in "$CLIENT_PRIVATE_KEY_FILE" -pubout \
    -out "$CLIENT_PUBLIC_KEY_FILE" 2>/dev/null

  echo "🚀 IBM Secure Embed: generate-key-pair"
  GEN_RESPONSE=$(curl -sS -X POST \
    "${SERVICE_INSTANCE_URL}/v1/embed/secure/generate-key-pair" \
    -H "IAM-API_KEY: ${IAM_API_KEY}" \
    -H "accept: application/json")

  ORCHESTRATE_ID=$(jq -r '.orchestrate_id' <<< "$GEN_RESPONSE")
  jq -r '.public_key' <<< "$GEN_RESPONSE" > "$IBM_PUBLIC_KEY_FILE"
fi

chmod 600 "$CLIENT_PRIVATE_KEY_FILE"
chmod 644 "$CLIENT_PUBLIC_KEY_FILE" "$IBM_PUBLIC_KEY_FILE"

CLIENT_PUBLIC_KEY_RAW=$(cat "$CLIENT_PUBLIC_KEY_FILE")
IBM_PUBLIC_KEY_RAW=$(cat "$IBM_PUBLIC_KEY_FILE")

CLIENT_PRIVATE_KEY_ENV=$(awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' "$CLIENT_PRIVATE_KEY_FILE")
CLIENT_PUBLIC_KEY_ENV=$(awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' "$CLIENT_PUBLIC_KEY_FILE")
IBM_PUBLIC_KEY_ENV=$(awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' "$IBM_PUBLIC_KEY_FILE")

# =========================================================
# Enable Secure Embed
# =========================================================
jq -n \
  --arg orchestrate_id "${ORCHESTRATE_ID:-existing}" \
  --arg client_public_key "$CLIENT_PUBLIC_KEY_RAW" \
  --arg ibm_public_key "$IBM_PUBLIC_KEY_RAW" \
  '{
    orchestrate_id: $orchestrate_id,
    client_public_key: $client_public_key,
    public_key: $ibm_public_key,
    is_security_enabled: true
  }' | curl -sS -X POST \
    "${SERVICE_INSTANCE_URL}/v1/embed/secure/config" \
    -H "Content-Type: application/json" \
    -H "IAM-API_KEY: ${IAM_API_KEY}" \
    -d @- | jq .



# =========================================================
# STEP 4–11: ORCHESTRATE + OKTA + MCP
# =========================================================
yes | $ORCHESTRATE_CMD env remove -n "$NAME_OF_INSTANCE" || true
$ORCHESTRATE_CMD env add -n "$NAME_OF_INSTANCE" -u "$SERVICE_INSTANCE_URL"
$ORCHESTRATE_CMD env activate "$NAME_OF_INSTANCE" --api-key "$IAM_API_KEY"

$ORCHESTRATE_CMD connections remove -a "$ORCHESTRATE_CONNECTION_APP_NAME" >/dev/null 2>&1 || true
$ORCHESTRATE_CMD connections add -a "$ORCHESTRATE_CONNECTION_APP_NAME"

$ORCHESTRATE_CMD connections configure \
  -a "$ORCHESTRATE_CONNECTION_APP_NAME" \
  --env draft \
  --type team \
  --kind bearer

$ORCHESTRATE_CMD toolkits remove -n "$ORCHESTRATE_MCP_TOOLKIT_NAME" || true

TOKEN_RESPONSE=$(curl -sS -X POST "$OKTA_TOKEN_URL" \
  -H "Accept: application/json" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=client_credentials" \
  --data-urlencode "client_id=${API_SERVICES_CLIENT_ID}" \
  --data-urlencode "client_secret=${API_SERVICES_CLIENT_SECRET}" \
  --data-urlencode "scope=${SCOPE}")

ACCESS_TOKEN=$(jq -r '.access_token' <<< "$TOKEN_RESPONSE")

$ORCHESTRATE_CMD connections set-credentials \
  -a "$ORCHESTRATE_CONNECTION_APP_NAME" \
  --env draft \
  --token "$ACCESS_TOKEN"

$ORCHESTRATE_CMD toolkits add \
  --kind mcp \
  --name "$ORCHESTRATE_MCP_TOOLKIT_NAME" \
  --description "$MCP_TOOLKIT_DESCRIPTION" \
  --url "$MCP_SERVER_URL" \
  --transport streamable_http \
  --tools "*" \
  --app-id "$ORCHESTRATE_CONNECTION_APP_NAME"

sed -i "" "s/^app_id:.*/app_id: ${ORCHESTRATE_CONNECTION_APP_NAME}/" \
  "${SCRIPT_DIR}/../connections/connection.yaml"

$ORCHESTRATE_CMD connections import -f "${SCRIPT_DIR}/../connections/connection.yaml"

$ORCHESTRATE_CMD connections set-credentials \
  --app-id "$ORCHESTRATE_CONNECTION_APP_NAME" \
  --env live \
  --client-id "$API_SERVICES_CLIENT_ID" \
  --grant-type "urn:ietf:params:oauth:grant-type:token-exchange" \
  --token-url "$OKTA_TOKEN_URL" \
  -t "body:client_secret=$API_SERVICES_CLIENT_SECRET" \
  -t "body:subject_token_type=urn:ietf:params:oauth:token-type:access_token" \
  -t "body:scope=$SCOPE" \
  -t "body:audience=$AUDIENCE" \
  -t "body:app_token_key=subject_token"

# =========================================================
# ADDITIONAL AGENT + EMBED STEPS (APPENDED)
# =========================================================

echo "📥 Importing agents..."

$ORCHESTRATE_CMD tools import -f "$SCRIPT_DIR/../tools/rbac_plugin.py" -k python
$ORCHESTRATE_CMD agents import -f "$SCRIPT_DIR/../agents/manager_agent.yaml"
$ORCHESTRATE_CMD agents import -f "$SCRIPT_DIR/../agents/general_agent.yaml"
$ORCHESTRATE_CMD agents import -f "$SCRIPT_DIR/../agents/hr_main_agent.yaml"


echo "🚀 Deploying agent..."
$ORCHESTRATE_CMD agents deploy -n hr_main_agent

echo "📦 Fetching webchat embed (live)..."
EMBED_OUTPUT=$(
  $ORCHESTRATE_CMD channels webchat embed \
    --agent-name hr_main_agent \
    --env live
)

ORCHESTRATION_ID=$(printf "%s\n" "$EMBED_OUTPUT" | grep 'orchestrationID' | head -n 1 | sed -E 's/.*"([^"]+)".*/\1/')
HOST_URL=$(printf "%s\n" "$EMBED_OUTPUT" | grep 'hostURL' | head -n 1 | sed -E 's/.*"([^"]+)".*/\1/')
CRN=$(printf "%s\n" "$EMBED_OUTPUT" | tr '\n' ' ' | sed -E 's/.*crn:[[:space:]]*"([^"]+)".*/\1/')
AGENT_ID=$(printf "%s\n" "$EMBED_OUTPUT" | grep 'agentId' | head -n 1 | sed -E 's/.*"([^"]+)".*/\1/')
AGENT_ENV_ID=$(printf "%s\n" "$EMBED_OUTPUT" | grep 'agentEnvironmentId' | head -n 1 | sed -E 's/.*"([^"]+)".*/\1/')

: "${ORCHESTRATION_ID:?missing orchestrationID}"
: "${HOST_URL:?missing hostURL}"
: "${CRN:?missing crn}"
: "${AGENT_ID:?missing agentId}"
: "${AGENT_ENV_ID:?missing agentEnvironmentId}"


# =========================================================
# Update .env (keys)
# =========================================================
write_env_var "NEXT_PUBLIC_CLIENT_PRIVATE_KEY" "$CLIENT_PRIVATE_KEY_ENV" "$ENV_OUTPUT_FILE"
write_env_var "NEXT_PUBLIC_CLIENT_PUBLIC_KEY"  "$CLIENT_PUBLIC_KEY_ENV"  "$ENV_OUTPUT_FILE"
write_env_var "NEXT_PUBLIC_IBM_PUBLIC_KEY"     "$IBM_PUBLIC_KEY_ENV"     "$ENV_OUTPUT_FILE"
write_env_var "NEXT_PUBLIC_SPA_CLIENT_ID" "$SPA_CLIENT_ID" "$ENV_OUTPUT_FILE"
write_env_var "NEXT_PUBLIC_OKTA_BASE_URL"        "$OKTA_BASE_URL"      "$ENV_OUTPUT_FILE"
write_env_var "NEXT_PUBLIC_ORCHESTRATE_ORCHESTRATIONID" "$ORCHESTRATION_ID" "$ENV_OUTPUT_FILE"
write_env_var "NEXT_PUBLIC_ORCHESTRATE_HOSTURL" "$HOST_URL" "$ENV_OUTPUT_FILE"
write_env_var "NEXT_PUBLIC_ORCHESTRATE_CRN" "$CRN" "$ENV_OUTPUT_FILE"
write_env_var "NEXT_PUBLIC_ORCHESTRATE_AGENT_ID" "$AGENT_ID" "$ENV_OUTPUT_FILE"
write_env_var "NEXT_PUBLIC_ORCHESTRATE_AGENT_ENVIRONMENT_ID" "$AGENT_ENV_ID" "$ENV_OUTPUT_FILE"

echo "✅ DONE: Secure Embed + Agent deployed + .env updated"
