#!/bin/bash

# IBM Verify Token Exchange Script
# Exchanges an existing access token for a new one using token exchange grant

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   IBM Verify Token Exchange           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"

# Configuration
CLIENT_ID="7f07b084-195f-4826-abb6-399f7b6cfae1"
CLIENT_SECRET="8Hqm8PbYsP77IGBO1zQl"
TENANT="https://confuseddeputy.verify.ibm.com"
TOKEN_ENDPOINT="${TENANT}/oauth2/token"

# Get current access token as command line argument or from clipboard
if [ -n "$1" ]; then
    CURRENT_TOKEN="$1"
    echo -e "${GREEN}✓ Token aus Argument übernommen${NC}"
else
    # Try to get from clipboard (macOS)
    if command -v pbpaste &> /dev/null; then
        echo -e "\n${YELLOW}Token aus Zwischenablage verwenden? (y/n)${NC}"
        read -n 1 -r REPLY
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            CURRENT_TOKEN=$(pbpaste)
            echo -e "${GREEN}✓ Token aus Zwischenablage übernommen${NC}"
        fi
    fi
    
    # If still no token, ask for manual input
    if [ -z "$CURRENT_TOKEN" ]; then
        echo -e "\n${YELLOW}Aktuellen Access Token eingeben:${NC}"
        echo -e "${YELLOW}(Tipp: Token kopieren, dann Ctrl+D drücken)${NC}"
        CURRENT_TOKEN=$(cat)
        # Remove any whitespace/newlines
        CURRENT_TOKEN=$(echo "$CURRENT_TOKEN" | tr -d '\n\r\t ' )
    fi
fi

if [ -z "$CURRENT_TOKEN" ]; then
    echo -e "${RED}✗ Kein Token eingegeben${NC}"
    exit 1
fi

# Perform token exchange
echo -e "\n${YELLOW}Token Exchange wird durchgeführt...${NC}"
echo -e "${YELLOW}Endpoint: ${TOKEN_ENDPOINT}${NC}"

RESPONSE=$(curl -k -s -X POST "${TOKEN_ENDPOINT}" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=urn:ietf:params:oauth:grant-type:token-exchange' \
  -d "client_id=${CLIENT_ID}" \
  -d "client_secret=${CLIENT_SECRET}" \
  -d "subject_token=${CURRENT_TOKEN}" \
  -d 'subject_token_type=urn:ietf:params:oauth:token-type:access_token' \
  -d 'scope=openid profile email')

# Check if response contains error
if echo "$RESPONSE" | grep -q '"error"'; then
    echo -e "${RED}✗ Token Exchange fehlgeschlagen${NC}"
    echo -e "${RED}Response:${NC}"
    echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
    exit 1
fi

# Extract new access token
NEW_ACCESS_TOKEN=$(echo "$RESPONSE" | jq -r '.access_token' 2>/dev/null)

if [ -z "$NEW_ACCESS_TOKEN" ] || [ "$NEW_ACCESS_TOKEN" = "null" ]; then
    echo -e "${RED}✗ Kein Access Token in Response${NC}"
    echo -e "${RED}Response:${NC}"
    echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
    exit 1
fi

echo -e "${GREEN}✓ Token Exchange erfolgreich${NC}"
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Neuer Access Token:${NC}"
echo -e "${YELLOW}${NEW_ACCESS_TOKEN}${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Copy to clipboard if available
if command -v pbcopy &> /dev/null; then
    echo "$NEW_ACCESS_TOKEN" | pbcopy
    echo -e "${GREEN}✓ Token in Zwischenablage kopiert${NC}"
fi

# Show full response
echo -e "\n${YELLOW}Vollständige Response:${NC}"
echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"

# Optional: Update MCP configuration
echo -e "\n${YELLOW}MCP Konfiguration aktualisieren? (y/n)${NC}"
read -n 1 -r UPDATE_MCP
echo ""

if [[ $UPDATE_MCP =~ ^[Yy]$ ]]; then
    MCP_CONFIG_PATH="$HOME/.bob/settings/mcp_settings.json"
    
    if [ -f "$MCP_CONFIG_PATH" ]; then
        cp "$MCP_CONFIG_PATH" "${MCP_CONFIG_PATH}.backup"
        jq --arg token "$NEW_ACCESS_TOKEN" \
           '.mcpServers["products-mcp"].headers.Authorization = "Bearer " + $token' \
           "$MCP_CONFIG_PATH" > "${MCP_CONFIG_PATH}.tmp" && \
        mv "${MCP_CONFIG_PATH}.tmp" "$MCP_CONFIG_PATH"
        echo -e "${GREEN}✓ MCP Konfiguration aktualisiert${NC}"
    else
        echo -e "${RED}✗ MCP Konfiguration nicht gefunden: ${MCP_CONFIG_PATH}${NC}"
    fi
fi

echo -e "\n${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Token Exchange abgeschlossen!     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"

# Made with Bob
