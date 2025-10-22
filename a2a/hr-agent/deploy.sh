#!/usr/bin/env bash
set -euo pipefail

############################################
# Config — change these to your values
############################################
RESOURCE_GROUP="itz-wxo-68dbad284f96931ccaa195"
PROJECT_NAME="ce-itz-wxo-68dbad284f96931ccaa195"
REGISTRY="us.icr.io"
REGISTRY_NAMESPACE="cr-itz-s147ho60"
HR_IMAGE="${REGISTRY}/${REGISTRY_NAMESPACE}/hr-agent-a2a:latest"
REGISTRY_SECRET="icr-secret"
PORT=8080

HR_APP="hr-agent-a2a"

# Public URL - will be set after deployment or use existing
HR_URL="${HR_URL:-https://hr-agent-a2a.206hm5j0cjd0.us-south.codeengine.appdomain.cloud}"

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

upsert_app () {
  local name="$1"
  local image="$2"
  local public_url="$3"

  if exists_app "$name"; then
    echo "Updating app: ${name}"
    ibmcloud ce application update \
      --name "$name" \
      --image "$image" \
      --registry-secret "$REGISTRY_SECRET" \
      --port "$PORT" \
      --env PUBLIC_URL="$public_url"
  else
    echo "Creating app: ${name}"
    ibmcloud ce application create \
      --name "$name" \
      --image "$image" \
      --registry-secret "$REGISTRY_SECRET" \
      --port "$PORT" \
      --cpu 0.5 \
      --memory 1G \
      --min-scale 0 \
      --max-scale 2 \
      --env PUBLIC_URL="$public_url"
  fi
}

############################################
# Login / Target
############################################
echo ">> Checking IBM Cloud login"
if ! ibmcloud target >/dev/null 2>&1; then
  echo "❌ Not logged in. Run: ibmcloud login --sso"
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
echo "Building & pushing HR Agent A2A image"
echo "========================================"
docker buildx build --platform linux/amd64 -t "$HR_IMAGE" --push .

############################################
# Create/Update App
############################################
echo "========================================"
echo "Deploying HR Agent A2A"
echo "========================================"
upsert_app "$HR_APP" "$HR_IMAGE" "$HR_URL"

############################################
# Wait & Test
############################################
echo ">> Waiting for app to become ready (30s)"
sleep 30

set +e
echo "========================================"
echo "Testing HR Agent A2A"
echo "========================================"

echo ""
echo "1. Agent Card (A2A Protocol Discovery)"
echo "   GET $HR_URL/.well-known/agent-card.json"
curl -sS --max-time 15 "$HR_URL/.well-known/agent-card.json" | jq .

echo ""
echo "2. Sample Task - Onboard Employee"
echo "   Testing with: 'Onboard Sarah Williams as a Software Engineer'"
curl -N -sS --max-time 30 "$HR_URL/tasks" \
  -H "content-type: application/json" \
  -d '{
        "messages": [
          {
            "role": "user",
            "content": [
              {
                "type": "text",
                "text": "Onboard Sarah Williams as a Software Engineer"
              }
            ]
          }
        ]
      }'
echo ""
echo ""

echo "========================================"
echo "Deployment Complete!"
echo "========================================"
echo "HR Agent URL: $HR_URL"
echo "Agent Card: $HR_URL/.well-known/agent-card.json"
echo ""
echo "You can now add this agent to Watsonx Orchestrate using the hr_agent.yaml file."
echo ""
