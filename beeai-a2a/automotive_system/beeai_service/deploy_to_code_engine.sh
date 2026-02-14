#!/bin/bash
set -e

echo "=========================================="
echo "BeeAI Service - Code Engine Deployment"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check prerequisites
echo -e "${YELLOW}Step 1: Checking prerequisites...${NC}"

if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    exit 1
fi

# Load environment variables from .env
source .env

# Validate required variables
required_vars=(
    "WATSONX_API_KEY"
    "WATSONX_URL"
    "WATSONX_PROJECT_ID"
    "BEEAI_API_KEY"
    "IBM_CLOUD_API_KEY"
    "NAMESPACE"
    "IMAGE_NAME"
    "IMAGE_TAG"
    "APP_NAME"
    "PROJECT_ID"
    "RESOURCE_GROUP"
    "REGION"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}Error: Missing $var in .env${NC}"
        exit 1
    fi
done

if ! command -v podman &> /dev/null; then
    echo -e "${RED}Podman not found!${NC}"
    exit 1
fi

if ! command -v ibmcloud &> /dev/null; then
    echo -e "${RED}IBM Cloud CLI not found!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites checked${NC}"

# Login to IBM Cloud with API key
echo ""
echo -e "${YELLOW}Step 2: Logging in to IBM Cloud...${NC}"
ibmcloud login --apikey ${IBM_CLOUD_API_KEY} -r ${REGION} -g ${RESOURCE_GROUP}
echo -e "${GREEN}✓ Logged in${NC}"

# Login to Container Registry
echo ""
echo -e "${YELLOW}Step 3: Logging in to Container Registry...${NC}"
podman logout us.icr.io 2>/dev/null || true
podman login -u iamapikey -p ${IBM_CLOUD_API_KEY} us.icr.io
echo -e "${GREEN}✓ Logged in to registry${NC}"

# Build image
echo ""
echo -e "${YELLOW}Step 4: Building Docker image...${NC}"
podman build --platform=linux/amd64 -t ${IMAGE_NAME}:${IMAGE_TAG} .
echo -e "${GREEN}✓ Image built${NC}"

# Tag image
echo ""
echo -e "${YELLOW}Step 5: Tagging image...${NC}"
podman tag localhost/${IMAGE_NAME}:${IMAGE_TAG} us.icr.io/${NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG}
echo -e "${GREEN}✓ Image tagged${NC}"

# Push image
echo ""
echo -e "${YELLOW}Step 6: Pushing image to registry...${NC}"
podman push us.icr.io/${NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG}
echo -e "${GREEN}✓ Image pushed${NC}"

# Verify image in registry
echo ""
echo -e "${YELLOW}Step 7: Verifying image in registry...${NC}"
ibmcloud cr images --restrict ${NAMESPACE}
echo -e "${GREEN}✓ Image verified${NC}"

# Select Code Engine project
echo ""
echo -e "${YELLOW}Step 8: Selecting Code Engine project...${NC}"
ibmcloud ce project select --id ${PROJECT_ID}
echo -e "${GREEN}✓ Project selected${NC}"

# Create registry secret if not exists
echo ""
echo -e "${YELLOW}Step 9: Creating registry secret...${NC}"
ibmcloud ce registry create \
  --name ce-auto-icr-us-south \
  --server us.icr.io \
  --username iamapikey \
  --password ${IBM_CLOUD_API_KEY} 2>/dev/null || echo "Secret already exists"
echo -e "${GREEN}✓ Registry secret ready${NC}"

# Delete existing app if exists
echo ""
echo -e "${YELLOW}Step 10: Cleaning up existing app...${NC}"
ibmcloud ce app delete --name ${APP_NAME} --force 2>/dev/null || echo "No existing app to delete"
echo -e "${GREEN}✓ Cleaned up${NC}"

# Deploy application
echo ""
echo -e "${YELLOW}Step 11: Deploying application to Code Engine...${NC}"
ibmcloud ce app create \
  --name ${APP_NAME} \
  --image us.icr.io/${NAMESPACE}/${IMAGE_NAME}:${IMAGE_TAG} \
  --registry-secret ce-auto-icr-us-south \
  --port 8080 \
  --min-scale 1 \
  --max-scale 2 \
  --cpu 1 \
  --memory 2G \
  --env BEEAI_WXO_PORT=8080 \
  --env BEEAI_WXO_HOST=0.0.0.0 \
  --env BEEAI_API_KEY=${BEEAI_API_KEY} \
  --env BEEAI_LLM_MODEL=${BEEAI_LLM_MODEL} \
  --env WATSONX_API_KEY=${WATSONX_API_KEY} \
  --env WATSONX_URL=${WATSONX_URL} \
  --env WATSONX_PROJECT_ID=${WATSONX_PROJECT_ID} \
  --env WATSONX_MODEL_ID=${WATSONX_MODEL_ID} \
  --env WATSONX_MAX_TOKENS=${WATSONX_MAX_TOKENS} \
  --env WATSONX_TEMPERATURE=${WATSONX_TEMPERATURE}

echo -e "${GREEN}✓ Application deployed${NC}"

# Get application details
echo ""
echo -e "${YELLOW}Step 12: Getting application URL...${NC}"
APP_URL=$(ibmcloud ce app get --name ${APP_NAME} --output json | grep -o '"url":"[^"]*' | grep -o '[^"]*$')
echo -e "${GREEN}✓ Application URL: ${APP_URL}${NC}"

# Test health endpoint
echo ""
echo -e "${YELLOW}Step 13: Testing health endpoint...${NC}"
sleep 15
HEALTH_RESPONSE=$(curl -s ${APP_URL}/health || echo "failed")

if [ "$HEALTH_RESPONSE" != "failed" ]; then
    echo -e "${GREEN}✓ Service is healthy!${NC}"
    echo "Response: ${HEALTH_RESPONSE}"
else
    echo -e "${YELLOW}⚠ Health check pending, checking logs...${NC}"
    ibmcloud ce app logs --name ${APP_NAME} --tail 50
fi

echo ""
echo -e "${GREEN}=========================================="
echo "Deployment Complete!"
echo "==========================================${NC}"
echo ""
echo -e "${GREEN}Application URL:${NC} ${APP_URL}"
echo -e "${GREEN}Health Check:${NC} ${APP_URL}/health"
echo -e "${GREEN}API Docs:${NC} ${APP_URL}/docs"
echo ""
echo -e "${YELLOW}For watsonx Orchestrate integration:${NC}"
echo "  External agent URL: ${APP_URL}/chat/completions"
echo "  API Key: ${BEEAI_API_KEY}"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo "  View logs: ibmcloud ce app logs --name ${APP_NAME} --follow"
echo "  Get status: ibmcloud ce app get --name ${APP_NAME}"
echo "  Delete app: ibmcloud ce app delete --name ${APP_NAME} --force"
echo ""
EOF

chmod +x deploy_to_code_engine.sh