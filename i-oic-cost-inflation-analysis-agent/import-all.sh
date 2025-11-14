#!/usr/bin/env bash
set -euo pipefail

#######################################
# Environment Configuration
#######################################

ENV_NAME="oictutorial"
WXO_URL="https://api.eu-central-1.dl.watson-orchestrate.ibm.com/instances/20250508-1435-1457-50e0-b8f069e11f66"
WXO_API_KEY="WXO_API_KEY"
GROQ_API_KEY="GROQ_API_KEY"
ANTHROPIC_API_KEY="ANTHROPIC_API_KEY"

#######################################
# Environment Setup
#######################################

# Add and activate orchestrate environment
orchestrate env add --name "$ENV_NAME" --url "$WXO_URL"
orchestrate env activate "$ENV_NAME" --api-key "$WXO_API_KEY"

#######################################
# Connections – Groq
#######################################

orchestrate connections add -a "groq_credentials"

# Configure for draft environment
orchestrate connections configure -a "groq_credentials" --env draft \
  -t team \
  -k key_value

orchestrate connections set-credentials -a "groq_credentials" --env draft \
  -e api_key="$GROQ_API_KEY"

# Configure for live environment
orchestrate connections configure -a "groq_credentials" --env live \
  -t team \
  -k key_value

orchestrate connections set-credentials -a "groq_credentials" --env live \
  -e api_key="$GROQ_API_KEY"

#######################################
# Connections – Anthropic
#######################################

orchestrate connections add -a "anthropic_credentials"

# Configure for draft
orchestrate connections configure -a "anthropic_credentials" --env draft \
  -t team \
  -k key_value

orchestrate connections set-credentials -a "anthropic_credentials" --env draft \
  -e api_key="$ANTHROPIC_API_KEY"

# Configure for live
orchestrate connections configure -a "anthropic_credentials" --env live \
  -t team \
  -k key_value

orchestrate connections set-credentials -a "anthropic_credentials" --env live \
  -e api_key="$ANTHROPIC_API_KEY"

#######################################
# Import Models
#######################################

orchestrate models import \
  --file models/groq-openai.yaml \
  --app-id groq_credentials

orchestrate models import \
  --file models/anthropic-claude.yaml \
  --app-id anthropic_credentials

#######################################
# Import Knowledge Base
#######################################

orchestrate knowledge-bases import \
  -f knowledge-bases/knowledge-base.yaml

#######################################
# Import Tools
#######################################

cd tools

orchestrate tools import -k python \
  -f oic_granite_summary_tool.py \
  -r requirements.txt

cd ..

#######################################
# Import Agents
#######################################

orchestrate agents import \
  --file agents/oic_cost_inflation_analysis_agent.yaml

orchestrate agents import \
  --file agents/oic_cost_insights_master_agent.yaml
