#!/usr/bin/env bash
set -euo pipefail

############################################
# Config — change these to your values
############################################
RESOURCE_GROUP="itz-wxo-68dbad284f96931ccaa195"
PROJECT_NAME="ce-itz-wxo-68dbad284f96931ccaa195"
REGISTRY="us.icr.io"
REGISTRY_NAMESPACE="cr-itz-s147ho60"
HR_IMAGE="${REGISTRY}/${REGISTRY_NAMESPACE}/hr-agent-pure-a2a:latest"
REGISTRY_SECRET="icr-secret"
PORT=8080

HR_APP="hr-agent-pure-a2a"

# Public URL - will be set after deployment
HR_URL="${HR_URL:-}"

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
      --port "$PORT"
  else
    echo "Creating app: ${name}"
    ibmcloud ce application create \
      --name "$name" \
      --image "$image" \
      --registry-secret "$REGISTRY_SECRET" \
      --port "$PORT" \
      --cpu 0.5 \
      --memory 1G \
      --min-scale 1 \
      --max-scale 2
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
echo "Building & pushing HR Agent Pure A2A image"
echo "========================================"
docker buildx build --platform linux/amd64 -f Dockerfile -t "$HR_IMAGE" --push .

############################################
# Create/Update App
############################################
echo "========================================"
echo "Deploying HR Agent Pure A2A"
echo "========================================"
upsert_app "$HR_APP" "$HR_IMAGE"

############################################
# Get the deployed URL
############################################
echo ">> Waiting for app to become ready (30s)"
sleep 30

HR_URL=$(get_app_url "$HR_APP")
echo "App deployed at: $HR_URL"

############################################
# Test
############################################
set +e
echo "========================================"
echo "Testing HR Agent Pure A2A"
echo "========================================"

echo ""
echo "1. Agent Card (A2A Protocol Discovery)"
echo "   GET $HR_URL/.well-known/agent-card.json"
curl -sS --max-time 15 "$HR_URL/.well-known/agent-card.json" | jq .

echo ""
echo "2. Health Check"
echo "   GET $HR_URL/health"
curl -sS --max-time 15 "$HR_URL/health" | jq .

echo ""
echo "3. Sample Task - Onboard Employee (A2A Protocol)"
echo "   Testing with: 'Onboard Sarah Williams as a Software Engineer'"
curl -N -sS --max-time 30 "$HR_URL/tasks" \
  -H "content-type: application/json" \
  -d '{
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
          "message": {
            "role": "user",
            "parts": [
              {
                "root": {
                  "text": "Onboard Sarah Williams as a Software Engineer"
                }
              }
            ]
          }
        },
        "id": 1
      }'
echo ""
echo ""

echo "========================================"
echo "Deployment Complete!"
echo "========================================"
echo "HR Agent Pure A2A URL: $HR_URL"
echo "Agent Card: $HR_URL/.well-known/agent-card.json"
echo "Health Check: $HR_URL/health"
echo ""
echo "You can now add this agent to Watsonx Orchestrate using the agent card URL."
echo ""
