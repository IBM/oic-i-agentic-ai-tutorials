#!/bin/bash
# Complete Setup and Test for Kafka MCP Integration with watsonx Orchestrate

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Kafka MCP + watsonx Orchestrate - Complete Setup       ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Configuration
TOOLKIT_NAME="kafka-consumer"
AGENT_NAME="kafka_inventory_agent"
MCP_URL="https://kafka-mcp-server.238me2skf8m1.us-south.codeengine.appdomain.cloud/sse"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}Prerequisites Check${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if orchestrate CLI is available
if ! command -v orchestrate &> /dev/null; then
    echo -e "${RED}ERROR${NC} orchestrate CLI not found"
    echo "Please install the watsonx Orchestrate CLI first"
    exit 1
fi
echo -e "${GREEN}OK${NC} orchestrate CLI found"

# Check if environment is activated
if ! orchestrate env list &> /dev/null; then
    echo -e "${YELLOW}WARNING${NC} orchestrate environment not activated"
    echo ""
    echo "Please activate your environment first:"
    echo "  orchestrate env activate <your-env-name>"
    echo ""
    exit 1
fi
echo -e "${GREEN}OK${NC} orchestrate environment is active"

echo ""
echo -e "${CYAN}Step 1: Register MCP Toolkit${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if toolkit already exists
if orchestrate toolkits list 2>/dev/null | grep -q "$TOOLKIT_NAME"; then
    echo -e "${YELLOW}WARNING${NC} Toolkit '$TOOLKIT_NAME' already exists"
    echo "Removing existing toolkit..."
    orchestrate toolkits remove --name "$TOOLKIT_NAME" 2>/dev/null || true
    sleep 2
fi

echo "Registering MCP toolkit at: $MCP_URL"
echo ""

if orchestrate toolkits add \
    --kind mcp \
    --name "$TOOLKIT_NAME" \
    --description "Kafka event consumer for inventory-events topic" \
    --url "$MCP_URL" \
    --transport sse \
    --tools "*"; then
    echo ""
    echo -e "${GREEN}OK${NC} Toolkit registered successfully"
else
    echo ""
    echo -e "${RED}ERROR${NC} Failed to register toolkit"
    exit 1
fi

echo ""
echo "Waiting for toolkit to initialize..."
sleep 3

echo ""
echo "Toolkit details:"
orchestrate toolkits list | grep -A 5 "$TOOLKIT_NAME" || true

echo ""
echo -e "${CYAN}Step 2: Import Agent${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Remove old agent if exists
if orchestrate agents list 2>/dev/null | grep -q "$AGENT_NAME"; then
    echo "Removing existing agent..."
    orchestrate agents remove --name "$AGENT_NAME" --kind native 2>/dev/null || true
    sleep 2
fi

echo "Importing agent from kafka-inventory-agent.yaml..."
if orchestrate agents import --file kafka-inventory-agent.yaml; then
    echo ""
    echo -e "${GREEN}OK${NC} Agent imported successfully"
else
    echo ""
    echo -e "${RED}ERROR${NC} Failed to import agent"
    exit 1
fi

echo ""
echo "Agent details:"
orchestrate agents list | grep -A 3 "$AGENT_NAME" || true

echo ""
echo -e "${CYAN}Step 3: Test MCP Server Connection${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Testing SSE endpoint..."
if timeout 3 curl -s -I "$MCP_URL" 2>&1 | grep -q "200 OK"; then
    echo -e "${GREEN}OK${NC} MCP server is responding"
else
    echo -e "${YELLOW}WARNING${NC} MCP server may not be responding (check Code Engine logs)"
fi

echo ""
echo -e "${CYAN}Step 4: Run Test Queries${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo -e "${BLUE}Test 1: Check queue size${NC}"
echo "Command: orchestrate chat --agent $AGENT_NAME --message \"How many events are in the queue?\""
echo ""
orchestrate chat --agent "$AGENT_NAME" --message "How many events are in the queue?"

echo ""
echo ""
echo -e "${BLUE}Test 2: Get next event${NC}"
echo "Command: orchestrate chat --agent $AGENT_NAME --message \"Show me the next inventory event\""
echo ""
orchestrate chat --agent "$AGENT_NAME" --message "Show me the next inventory event"

echo ""
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}Setup and Testing Complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Your Kafka MCP integration is ready!"
echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo ""
echo "1. Start an interactive chat session:"
echo "   ${YELLOW}orchestrate chat --agent $AGENT_NAME${NC}"
echo ""
echo "2. Try these sample questions:"
echo "   - How many events are buffered?"
echo "   - Show me the next inventory event"
echo "   - Get the latest 5 events"
echo "   - What inventory changes happened recently?"
echo ""
echo "3. View agent details:"
echo "   ${YELLOW}orchestrate agents get --name $AGENT_NAME${NC}"
echo ""
echo "4. View toolkit details:"
echo "   ${YELLOW}orchestrate toolkits list | grep $TOOLKIT_NAME${NC}"
echo ""
echo "5. Check Code Engine logs:"
echo "   ${YELLOW}ibmcloud ce app logs --name kafka-mcp-server --follow${NC}"
echo ""
