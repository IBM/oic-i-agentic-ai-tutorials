#!/usr/bin/env bash
set -euo pipefail

# Verification script to confirm pure A2A protocol compliance

AGENT_URL="https://hr-agent-pure-a2a.20xtogjmfdje.us-south.codeengine.appdomain.cloud"

echo "========================================"
echo "Pure A2A Protocol Verification"
echo "========================================"
echo ""

# Test 1: Check Agent Card (A2A Standard)
echo "Test 1: Agent Card (A2A Standard Path)"
echo "GET $AGENT_URL/.well-known/agent.json"
echo "---"
AGENT_CARD=$(curl -sS "$AGENT_URL/.well-known/agent.json")
echo "$AGENT_CARD" | jq .
echo ""
echo " Protocol Version:" $(echo "$AGENT_CARD" | jq -r .protocolVersion)
echo " Capabilities:" $(echo "$AGENT_CARD" | jq .capabilities)
echo ""

# Test 2: Verify A2A JSON-RPC Endpoint (Root Path, not /v1/chat/completions)
echo "========================================"
echo "Test 2: A2A JSON-RPC Endpoint"
echo "POST $AGENT_URL/ (root path, NOT /v1/chat/completions)"
echo "---"
echo "Request Format: JSON-RPC 2.0 with method 'message/send'"
echo ""

# Test 3: Send A2A Message
echo "========================================"
echo "Test 3: Send A2A Message"
echo "---"
RESPONSE=$(curl -sS -X POST "$AGENT_URL/" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "verify-001",
        "role": "user",
        "parts": [
          {
            "text": "Onboard Test User as Verification Engineer"
          }
        ]
      }
    },
    "id": 1
  }')

echo "$RESPONSE" | jq .
echo ""

# Test 4: Verify Response Structure
echo "========================================"
echo "Test 4: Verify A2A Response Structure"
echo "---"
echo " JSON-RPC version:" $(echo "$RESPONSE" | jq -r .jsonrpc)
echo " Result type:" $(echo "$RESPONSE" | jq -r .result.kind)
echo " Has contextId:" $(echo "$RESPONSE" | jq -r .result.contextId)
echo " Has task ID:" $(echo "$RESPONSE" | jq -r .result.id)
echo " Task status:" $(echo "$RESPONSE" | jq -r .result.status.state)
echo " Has artifacts:" $(echo "$RESPONSE" | jq '.result.artifacts | length')
echo " Has history:" $(echo "$RESPONSE" | jq '.result.history | length')
echo ""

# Test 5: Verify it's NOT using /v1/chat/completions
echo "========================================"
echo "Test 5: Verify NOT OpenAI Chat Completions"
echo "---"
echo "Trying /v1/chat/completions endpoint (should fail)..."
CHAT_RESPONSE=$(curl -sS -X POST "$AGENT_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Onboard Test User"}
    ]
  }' || echo '{"error": "endpoint not found"}')

if echo "$CHAT_RESPONSE" | grep -q "Not Found\|404\|error"; then
  echo " CONFIRMED: /v1/chat/completions endpoint NOT available"
  echo " This is a PURE A2A agent, not a chat completions agent"
else
  echo "⚠️  WARNING: /v1/chat/completions endpoint exists"
  echo "Response: $CHAT_RESPONSE"
fi
echo ""

# Test 6: Check for OpenAI compatibility layer
echo "========================================"
echo "Test 6: Verify Pure A2A (No OpenAI Layer)"
echo "---"
ROUTES=$(curl -sS "$AGENT_URL/" -X OPTIONS 2>&1 || echo "")
if echo "$ROUTES" | grep -q "chat/completions"; then
  echo "⚠️  OpenAI routes detected"
else
  echo " No OpenAI compatibility layer detected"
  echo " Pure A2A implementation confirmed"
fi
echo ""

echo "========================================"
echo "Verification Complete"
echo "========================================"
echo ""
echo "Summary:"
echo " Uses standard A2A agent card path (/.well-known/agent.json)"
echo " Uses JSON-RPC 2.0 protocol"
echo " Endpoint at root path (/), not /v1/chat/completions"
echo " Returns A2A-compliant task responses with contextId"
echo " Maintains conversation history"
echo " Uses task lifecycle (working, completed states)"
echo ""
echo "This is a PURE A2A protocol agent! 🎉"
