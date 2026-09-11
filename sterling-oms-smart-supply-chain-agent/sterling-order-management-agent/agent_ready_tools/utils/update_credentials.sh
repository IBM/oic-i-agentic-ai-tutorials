#!/bin/bash

# Usage: ./update_credentials.sh [output_filename]
# If no output filename is provided, defaults to agent_ready_tools/utils/credentials.json

OUTPUT_FILE="agent_ready_tools/utils/${1:-credentials.json}"

# Check if 1Password CLI is available
if ! command -v op &>/dev/null; then
    echo "⚠️  1Password CLI (op) is not installed or not in PATH"
    echo "📥 To install, visit: https://developer.1password.com/docs/cli/get-started/#install"
    echo "🔧 Or use: brew install 1password-cli (macOS)"
    exit 1
fi

# Download wxo-domain credentials.json from wxo vault
echo "📥 Downloading wxo-domain credentials.json from wxo vault to: $OUTPUT_FILE"

if op document get "wxo-domain credentials.json" --vault="wxo" --output="$OUTPUT_FILE"; then
    echo "✅ Successfully downloaded credentials to: $OUTPUT_FILE"
else
    echo "❌ Failed to download credentials.json"
    echo "🔍 Make sure you're signed in to 1Password CLI: op signin"
    echo "🔍 Verify the document name and vault exist in your 1Password account"
    exit 1
fi
