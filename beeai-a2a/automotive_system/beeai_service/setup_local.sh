#!/bin/bash
set -e

echo "====================================="
echo "BeeAI Service Local Setup Script "
echo "====================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: docker-compose.yml not found!${NC}"
    echo "Please run this script from your beeai_service directory"
    exit 1
fi

echo -e "${YELLOW}Step 1: Checking prerequisites...${NC}"

# Check if podman is installed
if ! command -v podman &> /dev/null; then
    echo -e "${RED}Podman is not installed. Please install Podman first.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Podman found${NC}"

# Check if .env file exists
echo ""
echo -e "${YELLOW}Step 2: Checking .env file...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo "Please create .env file with required credentials"
    exit 1
fi
echo -e "${GREEN}✓ .env file found${NC}"

# Validate required environment variables
source .env
required_vars=("WATSONX_API_KEY" "WATSONX_URL" "WATSONX_PROJECT_ID" "BEEAI_API_KEY")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo -e "${RED}Error: Missing required environment variables in .env:${NC}"
    for var in "${missing_vars[@]}"; do
        echo -e "${RED}  - $var${NC}"
    done
    exit 1
fi
echo -e "${GREEN}✓ All required environment variables found${NC}"

echo ""
echo -e "${YELLOW}Step 3: Cleaning up old containers...${NC}"
podman-compose down -v 2>/dev/null || podman compose down -v 2>/dev/null || true
echo -e "${GREEN}✓ Cleaned up${NC}"

echo ""
echo -e "${YELLOW}Step 4: Removing old images...${NC}"
podman rmi beeai_service-beeai-service 2>/dev/null || echo "No old image to remove"

echo ""
echo -e "${YELLOW}Step 5: Building container...${NC}"
podman-compose build --no-cache 2>/dev/null || podman compose build --no-cache

echo ""
echo -e "${YELLOW}Step 6: Starting service...${NC}"
podman-compose up -d 2>/dev/null || podman compose up -d

echo ""
echo -e "${YELLOW}Step 7: Waiting for service to be ready...${NC}"
sleep 5

# Check if service is running
if podman ps | grep -q beeai_maintenance_service; then
    echo -e "${GREEN}✓ Container is running${NC}"
    
    # Check health
    echo ""
    echo -e "${YELLOW}Checking health endpoint...${NC}"
    sleep 2
    
    HEALTH_CHECK=$(curl -s http://localhost:8080/health 2>/dev/null || echo "failed")
    
    if [ "$HEALTH_CHECK" != "failed" ]; then
        echo -e "${GREEN}✓ Service is healthy!${NC}"
        echo ""
        echo "Response: $HEALTH_CHECK"
    else
        echo -e "${YELLOW}⚠ Health check failed, checking logs...${NC}"
        echo ""
        podman-compose logs --tail=20 2>/dev/null || podman compose logs --tail=20
    fi
else
    echo -e "${RED}✗ Container failed to start${NC}"
    echo ""
    echo "Checking logs:"
    podman-compose logs --tail=30 2>/dev/null || podman compose logs --tail=30
    exit 1
fi

echo ""
echo -e "${GREEN}=================================="
echo "Setup Complete!"
echo "==================================${NC}"
echo ""
echo "Service is running at: http://localhost:8080"
echo "API Documentation: http://localhost:8080/docs"
echo ""
echo "View logs: podman compose logs -f"
echo "Stop service: podman compose down"
echo ""
echo -e "${YELLOW}Test the service with:${NC}"
echo 'curl http://localhost:8080/health'
echo ""
