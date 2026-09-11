#!/bin/bash

# Script to generate RSA key pair for Watson Orchestrate JWT integration
# Outputs base64-encoded keys that can be added to .env file

set -e

echo "Generating RSA key pair for Watson Orchestrate integration..."
echo ""

# Create keys directory if it doesn't exist
KEYS_DIR="local/keys"
mkdir -p "$KEYS_DIR"

# Generate RSA private key (2048 bits)
openssl genrsa -out "$KEYS_DIR/private.pem" 2048 2>/dev/null

# Extract public key from private key
openssl rsa -in "$KEYS_DIR/private.pem" -pubout -out "$KEYS_DIR/public.pem" 2>/dev/null

echo "✅ Keys saved to:"
echo "   - $KEYS_DIR/private.pem (YOUR private key - keep it secret!)"
echo "   - $KEYS_DIR/public.pem (YOUR public key - upload this to Watson Orchestrate)"
echo ""

# Base64 encode the keys (single line, no wrapping)
PRIVATE_KEY_BASE64=$(base64 < "$KEYS_DIR/private.pem" | tr -d '\n')
PUBLIC_KEY_BASE64=$(base64 < "$KEYS_DIR/public.pem" | tr -d '\n')

# Check if wxo-public.pem or wxo_public.pem exists for WXO_PUBLIC_KEY_BASE64
if [ -f "$KEYS_DIR/wxo-public.pem" ]; then
    WXO_PUBLIC_KEY_BASE64=$(base64 < "$KEYS_DIR/wxo-public.pem" | tr -d '\n')
elif [ -f "$KEYS_DIR/wxo_public.pem" ]; then
    WXO_PUBLIC_KEY_BASE64=$(base64 < "$KEYS_DIR/wxo_public.pem" | tr -d '\n')
else
    WXO_PUBLIC_KEY_BASE64=""
    echo "⚠️  Note: $KEYS_DIR/wxo-public.pem not found."
    echo "   If you need to encrypt data for WxO, place their public key there."
    echo ""
fi

echo "=================================================="
echo "Add these lines to your .env file:"
echo "=================================================="
echo ""
echo "JWT_PRIVATE_KEY_BASE64=\"$PRIVATE_KEY_BASE64\""
echo ""
if [ -n "$WXO_PUBLIC_KEY_BASE64" ]; then
    echo "WXO_PUBLIC_KEY_BASE64=\"$WXO_PUBLIC_KEY_BASE64\""
else
    echo "# WXO_PUBLIC_KEY_BASE64=\"\" # Add Watson Orchestrate's public key here if needed"
fi
echo ""
echo "=================================================="
echo ""
echo "📋 Next steps:"
echo "   1. Copy the JWT_PRIVATE_KEY_BASE64 value to your .env file"
echo "   2. Upload $KEYS_DIR/public.pem to Watson Orchestrate admin console"
echo "   3. Configure the issuer (iss) in Watson Orchestrate to match your backend"
echo "   4. If encrypting data for WxO, get their public key and save as $KEYS_DIR/wxo-public.pem"
echo ""