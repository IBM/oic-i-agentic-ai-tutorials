#!/bin/bash
set -euo pipefail

# ============================================
# Parameter Validation
# ============================================
if [ $# -ne 1 ]; then
    echo "❌ Error: Orchestrate environment parameter is required"
    echo ""
    echo "Usage: $0 <orchestrate_environment>"
    echo ""
    echo "Arguments:"
    echo "  orchestrate_environment    The Orchestrate environment to activate"
    exit 1
fi

ORCHESTRATE_ENV="$1"

echo "🚀 Starting connection setup"
echo ""

source .env

echo "Activating Orchestrate environment: $ORCHESTRATE_ENV"
orchestrate env activate $ORCHESTRATE_ENV --api-key $API_KEY

# ============================================
# Token Exchange - Get Real Access Token
# ============================================
echo "🔐 Performing token exchange to get real access token..."


# Perform token exchange to get a fresh access token
TOKEN_RESPONSE=$(curl -k -s -X POST "${token_url}" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "grant_type=client_credentials" \
  -d "client_id=${app_client_id}" \
  -d "client_secret=${app_secret}" \
  -d "subject_token=${subject_token}" \
  -d "subject_token_type=${subject_token_type}" \
  -d "scope=${scope}" \
  -d "requested_token_use=${requested_token_use}")

# Check if token exchange was successful
if echo "$TOKEN_RESPONSE" | grep -q '"error"'; then
    echo "❌ Token exchange failed:"
    echo "$TOKEN_RESPONSE" | jq . 2>/dev/null || echo "$TOKEN_RESPONSE"
    exit 1
fi

# Extract the new access token
REAL_ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token' 2>/dev/null)

if [ -z "$REAL_ACCESS_TOKEN" ] || [ "$REAL_ACCESS_TOKEN" = "null" ]; then
    echo "❌ Failed to extract access token from response"
    echo "$TOKEN_RESPONSE" | jq . 2>/dev/null || echo "$TOKEN_RESPONSE"
    exit 1
fi

echo "✅ Token exchange successful!"
echo "📋 Access Token: ${REAL_ACCESS_TOKEN:0:50}..."

# Update the subject_token with the real access token for the connection setup
subject_token="$REAL_ACCESS_TOKEN"

# ============================================
# Create and Configure Orchestrate Connection
# ============================================

# Check if connection exists before trying to remove it
echo "🔍 Checking if connection exists..."
if orchestrate connections list -a $APP_ID 2>/dev/null | grep -q "$APP_ID"; then
    echo "📝 Connection exists, removing it..."
    orchestrate connections remove -a $APP_ID
else
    echo "ℹ️  No existing connection found, skipping removal"
fi

echo "➕ Adding new connection..."
orchestrate connections add -a $APP_ID

orchestrate connections configure -a $APP_ID \
--env draft --type member --kind oauth_auth_token_exchange_flow \
--server-url $server_url --sso

echo $token_url
echo $grant_type

orchestrate connections set-credentials -a $APP_ID \
--env draft --client-id $agent_app_client_id \
--grant-type $grant_type --token-url $token_url \
 -t "body:client_secret=${agent_app_secret}" \
 -t "body:subject_token_type=urn:ietf:params:oauth:token-type:access_token" \
 -t "body:scope=${scope}" \
 -t "body:requested_token_use=${requested_token_use}" \
 -t "body:subject_token=${subject_token}"

orchestrate connections configure -a $APP_ID \
--env live --type member --kind oauth_auth_token_exchange_flow \
--server-url $server_url --sso

orchestrate connections set-credentials -a $APP_ID \
--env live --client-id $agent_app_client_id \
--grant-type $grant_type --token-url $token_url \
 -t "body:client_secret=${agent_app_secret}" \
 -t "body:subject_token_type=${subject_token_type}" \
 -t "body:scope=${scope}" \
 -t "body:requested_token_use=${requested_token_use}" \
 -t "body:app_token_key=subject_token"

# ============================================
# Expected Error Notice
# ============================================
echo ""
echo "ℹ️  NOTE: You may see an error message like:"
echo "   [ERROR] - {\"success\":false,\"statusCode\":400,\"errorCode\":\"CM-UNKNOWN-001\","
echo "   \"message\":\"For SSO applications, manual entry is not allowed\"...}"
echo ""
echo "   This error can be safely IGNORED. The connection setup works correctly"
echo "   despite this error message appearing during the SSO configuration."
echo "============================================"
