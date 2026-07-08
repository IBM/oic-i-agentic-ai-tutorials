#!/bin/bash

# JWT Token Decoder
# This script decodes a JWT token to show its claims

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        JWT Token Decoder               ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"


# Check if token is provided as argument, otherwise prompt for it
if [ -z "$1" ]; then
    echo -e "${YELLOW}Please provide JWT token:${NC}"
    read -r MY_TOKEN
else
    MY_TOKEN="$1"
fi

if [ -z "$MY_TOKEN" ]; then
    echo -e "${RED}Error: No token provided${NC}"
    exit 1
fi

echo -e "\n${GREEN}Token received${NC}"

# Decode JWT (split by dots and decode the payload)
PAYLOAD=$(echo "$MY_TOKEN" | cut -d. -f2)

# Add padding if needed
case $((${#PAYLOAD} % 4)) in
    2) PAYLOAD="${PAYLOAD}==" ;;
    3) PAYLOAD="${PAYLOAD}=" ;;
esac

# Decode base64
DECODED=$(echo "$PAYLOAD" | base64 -d 2>/dev/null || echo "$PAYLOAD" | base64 -D 2>/dev/null)

echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}JWT Token Claims:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if command -v jq &> /dev/null; then
    echo "$DECODED" | jq .
else
    echo "$DECODED"
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Extract and highlight the issuer
ISSUER=$(echo "$DECODED" | python3 -c "import sys, json; print(json.load(sys.stdin).get('iss', 'NOT FOUND'))" 2>/dev/null)
AUDIENCE=$(echo "$DECODED" | python3 -c "import sys, json; print(json.load(sys.stdin).get('aud', 'NOT FOUND'))" 2>/dev/null)

echo -e "\n${GREEN}Key Claims:${NC}"
echo -e "${YELLOW}  Issuer (iss):${NC}   ${ISSUER}"
echo -e "${YELLOW}  Audience (aud):${NC} ${AUDIENCE}"

echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}MCP Server Configuration Required:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}JWT_ISSUER=${NC}${ISSUER}"
echo -e "${GREEN}JWT_AUDIENCE=${NC}${AUDIENCE}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Made with Bob