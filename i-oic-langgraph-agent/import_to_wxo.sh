#!/bin/bash

# Script to create and configure WatsonX Orchestrate connection for LangGraph agent
# This script will prompt for required credentials

echo "=========================================="
echo "WatsonX Orchestrate Connection Setup"
echo "=========================================="
echo ""

# Prompt for WatsonX Orchestrate URL
read -p "Enter your WatsonX Orchestrate instance URL: " WXO_LANGGRAPH_URL
if [ -z "$WXO_LANGGRAPH_URL" ]; then
    echo "Error: WatsonX Orchestrate URL is required"
    exit 1
fi

# Prompt for WatsonX Orchestrate API Key
read -sp "Enter your WatsonX Orchestrate API Key: " WXO_LANGGRAPH_API_KEY
echo ""
if [ -z "$WXO_LANGGRAPH_API_KEY" ]; then
    echo "Error: WatsonX Orchestrate API Key is required"
    exit 1
fi

echo ""
echo "Creating connection with provided credentials..."
echo ""

# Create connection
orchestrate connections add --app-id wxo_langgraph 

# Configure connection for draft environment
orchestrate connections configure \
    --app-id wxo_langgraph \
    --env draft \
    --type team \
    --kind key_value 

# Configure connection for live environment
orchestrate connections configure \
    --app-id wxo_langgraph \
    --env live \
    --type team \
    --kind key_value 

# Set credentials for draft environment
orchestrate connections set-credentials \
    --app-id wxo_langgraph \
    --env draft \
    -e base_url="$WXO_LANGGRAPH_URL" \
    -e api_key="$WXO_LANGGRAPH_API_KEY"

# Set credentials for live environment
orchestrate connections set-credentials \
    --app-id wxo_langgraph \
    --env live \
    -e base_url="$WXO_LANGGRAPH_URL" \
    -e api_key="$WXO_LANGGRAPH_API_KEY"

echo ""
echo "Importing agent..."
echo ""

# Import the agent
orchestrate agents import --package-root my_langraph_agent --config-file my_langraph_agent/agent.yaml

echo ""
echo "Connecting agent to connection..."
echo ""

# Connect agent to connection
orchestrate agents connect -n my_langraph_agent -a wxo_langgraph

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo "Agent 'my_langraph_agent' has been created and connected to the 'wxo_langgraph' connection."
echo ""

# Made with Bob
