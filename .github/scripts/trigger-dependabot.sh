#!/bin/bash

# Script to manually trigger Dependabot checks
# Usage: ./trigger-dependabot.sh [GITHUB_TOKEN]

# Don't exit on errors - we'll handle them gracefully
set +e

# Try to get repo info from git, with fallback
REPO_OWNER=$(git config --get remote.origin.url 2>/dev/null | sed -n 's/.*github.com[:/]\([^/]*\)\/.*/\1/p')
REPO_NAME=$(git config --get remote.origin.url 2>/dev/null | sed -n 's/.*github.com[:/][^/]*\/\([^.]*\).*/\1/p')

# Fallback to hardcoded values if git fails
if [ -z "$REPO_OWNER" ] || [ -z "$REPO_NAME" ]; then
    REPO_OWNER="IBM"
    REPO_NAME="oic-i-agentic-ai-tutorials"
fi

if [ -z "$1" ]; then
    echo "Error: GitHub token required"
    echo "Usage: $0 <GITHUB_TOKEN>"
    echo ""
    echo "Create a token at: https://github.com/settings/tokens"
    echo "Required scopes: repo, security_events"
    exit 1
fi

GITHUB_TOKEN="$1"

echo "Repository: $REPO_OWNER/$REPO_NAME"
echo "Triggering Dependabot updates..."
echo ""

# Note: GitHub doesn't provide a direct API to trigger Dependabot on-demand
# This script provides useful commands instead

echo "📋 Method 1: Via GitHub Web UI"
echo "Visit: https://github.com/$REPO_OWNER/$REPO_NAME/network/updates"
echo ""

echo "📋 Method 2: Check current alerts"
curl -s -H "Authorization: token $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github.v3+json" \
     "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/dependabot/alerts" | \
     jq -r '.[] | "- [\(.security_advisory.severity)] \(.security_advisory.summary) (\(.dependency.package.name))"'

echo ""
echo "📋 Method 3: View Dependabot status"
curl -s -H "Authorization: token $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github.v3+json" \
     "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/vulnerability-alerts"

echo ""
echo "✅ To manually trigger Dependabot:"
echo "1. Go to: https://github.com/$REPO_OWNER/$REPO_NAME/network/updates"
echo "2. Click 'Check for updates' for each package ecosystem"
