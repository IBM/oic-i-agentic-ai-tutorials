#!/usr/bin/env bash
set -euo pipefail

############################################
# Config — change these to your values
############################################
RESOURCE_GROUP="itz-wxo-68c293dc1642d9f9c32780"
PROJECT_NAME="ce-itz-wxo-68c293dc1642d9f9c32780"
REGISTRY="us.icr.io"
REGISTRY_NAMESPACE="cr-itz-8y7jh5y9"
LLM_IMAGE="${REGISTRY}/${REGISTRY_NAMESPACE}/granite-llm-server:latest"
REGISTRY_SECRET="icr-secret"
PORT=8080

LLM_APP="granite-llm-server"

# Authentication token for the LLM API (change this!)
AUTH_TOKEN="${AUTH_TOKEN:-change-me-to-secure-token}"

# Model to use (can be overridden)
MODEL_NAME="${MODEL_NAME:-ibm-granite/granite-4.0-h-1b}"

# Public URL - will be set after deployment
LLM_URL="${LLM_URL:-}"

############################################
# Helpers
############################################
exists_app () {
  local name="$1"
  if ibmcloud ce application get --name "$name" >/dev/null 2>&1; then
    return 0
  else
    return 1
  fi
}

get_app_url () {
  local name="$1"
  ibmcloud ce application get --name "$name" --output json | jq -r '.status.url'
}

upsert_app () {
  local name="$1"
  local image="$2"

  if exists_app "$name"; then
    echo "Updating app: ${name}"
    ibmcloud ce application update \
      --name "$name" \
      --image "$image" \
      --registry-secret "$REGISTRY_SECRET" \
      --port "$PORT" \
      --env MODEL_NAME="$MODEL_NAME" \
      --env AUTH_TOKEN="$AUTH_TOKEN"
  else
    echo "Creating app: ${name}"
    ibmcloud ce application create \
      --name "$name" \
      --image "$image" \
      --registry-secret "$REGISTRY_SECRET" \
      --port "$PORT" \
      --cpu 2 \
      --memory 8G \
      --min-scale 1 \
      --max-scale 2 \
      --env MODEL_NAME="$MODEL_NAME" \
      --env AUTH_TOKEN="$AUTH_TOKEN"
  fi
}

############################################
# Login / Target
############################################
echo ">> Checking IBM Cloud login"
if ! ibmcloud target >/dev/null 2>&1; then
  echo " Not logged in. Run: ibmcloud login --sso"
  exit 1
fi

echo ">> Targeting resource group and project"
ibmcloud target -g "$RESOURCE_GROUP"
ibmcloud ce project select -n "$PROJECT_NAME"

echo ">> Logging in to container registry"
ibmcloud cr login

############################################
# Build & Push Image
############################################
echo "========================================"
echo "Building & pushing Granite LLM Server image"
echo "========================================"
docker buildx build --platform linux/amd64 -f Dockerfile -t "$LLM_IMAGE" --push .

############################################
# Create/Update App
############################################
echo "========================================"
echo "Deploying Granite LLM Server"
echo "========================================"
echo "Model: $MODEL_NAME"
echo "Auth Token: ${AUTH_TOKEN:0:10}..."
upsert_app "$LLM_APP" "$LLM_IMAGE"

############################################
# Get the deployed URL
############################################
echo ">> Waiting for app to become ready (60s for model download)"
sleep 60

LLM_URL=$(get_app_url "$LLM_APP")
echo "App deployed at: $LLM_URL"

############################################
# Test
############################################
set +e
echo "========================================"
echo "Testing Granite LLM Server"
echo "========================================"

echo ""
echo "1. Health Check"
echo "   GET $LLM_URL/health"
curl -sS --max-time 15 "$LLM_URL/health" | jq .

echo ""
echo "2. Chat Completion Test"
echo "   Testing with: 'What is 2+2?'"
curl -N -sS --max-time 60 "$LLM_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
        "messages": [
          {
            "role": "user",
            "content": "What is 2+2?"
          }
        ],
        "max_tokens": 100,
        "temperature": 0.3
      }' | jq .

echo ""
echo ""

echo "========================================"
echo "Deployment Complete!"
echo "========================================"
echo "Granite LLM Server URL: $LLM_URL"
echo "Health Check: $LLM_URL/health"
echo "Chat Endpoint: $LLM_URL/v1/chat/completions"
echo ""
echo "Model: $MODEL_NAME"
echo "Auth Token: ${AUTH_TOKEN:0:10}..."
echo ""
echo "Usage example:"
echo ""
echo "curl -X POST $LLM_URL/v1/chat/completions \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -H 'Authorization: Bearer $AUTH_TOKEN' \\"
echo "  -d '{\"messages\": [{\"role\": \"user\", \"content\": \"Hello!\"}]}'"
echo ""
