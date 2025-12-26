#!/bin/bash
# Deploy Kafka MCP Server to IBM Code Engine

set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Deploy Kafka MCP Server to IBM Code Engine             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Configuration
PROJECT_NAME="ce-itz-wxo-6928646bfc4a8441fbed1d"
APP_NAME="kafka-mcp-server"
IMAGE_NAME="kafka-mcp-server"
REGION="us-south"  # Change if needed

# Load environment variables
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    echo "   Create .env with your Kafka credentials:"
    echo "   BOOTSTRAP_SERVER=your-broker.confluent.cloud:9092"
    echo "   API_KEY=your-api-key"
    echo "   API_SECRET=your-api-secret"
    exit 1
fi

source .env

# Validate required variables
if [ -z "$BOOTSTRAP_SERVER" ] || [ -z "$API_KEY" ] || [ -z "$API_SECRET" ]; then
    echo "Error: Missing required environment variables in .env"
    echo "   Required: BOOTSTRAP_SERVER, API_KEY, API_SECRET"
    exit 1
fi

echo "Environment variables loaded"
echo ""

# Check if logged in to IBM Cloud
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1: Verify IBM Cloud login"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if ! ibmcloud target &>/dev/null; then
    echo "Not logged in to IBM Cloud"
    echo "   Run: ibmcloud login"
    exit 1
fi

echo "Logged in to IBM Cloud"
ibmcloud target
echo ""

# Get Container Registry namespace
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2: Get Container Registry namespace"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# List namespaces
NAMESPACES=$(ibmcloud cr namespace-list -q)

if [ -z "$NAMESPACES" ]; then
    echo "No Container Registry namespace found."
    echo -n "Enter a name for new namespace: "
    read NAMESPACE
    echo "Creating namespace: $NAMESPACE"
    ibmcloud cr namespace-add "$NAMESPACE"
else
    echo "Available namespaces:"
    echo "$NAMESPACES"
    echo ""
    echo -n "Enter namespace to use (or press Enter for first one): "
    read NAMESPACE

    if [ -z "$NAMESPACE" ]; then
        NAMESPACE=$(echo "$NAMESPACES" | head -n 1)
    fi
fi

echo "Using namespace: $NAMESPACE"
echo ""

# Set registry URL
REGISTRY_REGION=$(ibmcloud cr region | grep "icr.io" | awk '{print $2}')
IMAGE_URL="${REGISTRY_REGION}/${NAMESPACE}/${IMAGE_NAME}:latest"
echo "Image will be: $IMAGE_URL"
echo ""

# Build Docker image
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3: Build Docker image"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

docker build -t "$IMAGE_NAME:latest" .
echo "Image built successfully"
echo ""

# Tag image for IBM Container Registry
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4: Tag and push image"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

docker tag "$IMAGE_NAME:latest" "$IMAGE_URL"
docker push "$IMAGE_URL"
echo "Image pushed to registry"
echo ""

# Create or select Code Engine project
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 5: Set up Code Engine project"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if project exists
if ibmcloud ce project get --name "$PROJECT_NAME" &>/dev/null; then
    echo "Project '$PROJECT_NAME' already exists"
    ibmcloud ce project select --name "$PROJECT_NAME"
else
    echo "Creating new project: $PROJECT_NAME"
    ibmcloud ce project create --name "$PROJECT_NAME"
fi

echo "Using project: $PROJECT_NAME"
echo ""

# Deploy application
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 6: Deploy application"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if app exists
if ibmcloud ce app get --name "$APP_NAME" &>/dev/null; then
    echo "Updating existing application: $APP_NAME"
    ibmcloud ce app update \
        --name "$APP_NAME" \
        --image "$IMAGE_URL" \
        --port 8080 \
        --env BOOTSTRAP_SERVER="$BOOTSTRAP_SERVER" \
        --env API_KEY="$API_KEY" \
        --env API_SECRET="$API_SECRET" \
        --min-scale 1 \
        --max-scale 2 \
        --cpu 0.25 \
        --memory 0.5G
else
    echo "Creating new application: $APP_NAME"
    ibmcloud ce app create \
        --name "$APP_NAME" \
        --image "$IMAGE_URL" \
        --port 8080 \
        --env BOOTSTRAP_SERVER="$BOOTSTRAP_SERVER" \
        --env API_KEY="$API_KEY" \
        --env API_SECRET="$API_SECRET" \
        --min-scale 1 \
        --max-scale 2 \
        --cpu 0.25 \
        --memory 0.5G
fi

echo ""
echo "Application deployed successfully"
echo ""

# Get application URL
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 7: Get application URL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

APP_URL=$(ibmcloud ce app get --name "$APP_NAME" --output json | grep -o '"url":"[^"]*' | sed 's/"url":"//')

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Deployment Complete!                                    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Application URL: $APP_URL"
echo ""
echo "Next steps:"
echo ""
echo "1. Test the MCP server:"
echo "   curl $APP_URL/sse"
echo ""
echo "2. Import to watsonx Orchestrate:"
echo "   orchestrate toolkits add \\"
echo "     --kind mcp \\"
echo "     --name kafka-consumer \\"
echo "     --description \"Kafka event consumer\" \\"
echo "     --url \"$APP_URL/sse\" \\"
echo "     --transport sse \\"
echo "     --tools \"*\""
echo ""
echo "3. Import your agent:"
echo "   orchestrate agents import --file kafka-inventory-agent.yaml"
echo ""
