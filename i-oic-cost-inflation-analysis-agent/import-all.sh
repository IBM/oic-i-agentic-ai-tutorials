#!/usr/bin/env bash
set -euo pipefail

#######################################
# Environment Configuration
#######################################

ENV_NAME="oictutorial"
WXO_URL="https://api.eu-central-1.dl.watson-orchestrate.ibm.com/instances/20250508-1435-1457-50e0-b8f069e11f66"
WXO_API_KEY=<WXO_API_KEY>
GROQ_API_KEY=<GROQ_API_KEY>
ANTHROPIC_API_KEY=<ANTHROPIC_API_KEY>
GRANITE_ROUTE_URL=<GRANITE_ROUTE_URL>

#######################################
# Environment Setup
#######################################

# Add and activate orchestrate environment
orchestrate env add --name "$ENV_NAME" --url "$WXO_URL"
orchestrate env activate "$ENV_NAME" --api-key "$WXO_API_KEY"

# # Connections 

orchestrate connections import \
  --file connections/connections.yaml

orchestrate connections set-credentials -a oic_llm_creds --env draft \
  -e "url_name=$GRANITE_ROUTE_URL"



orchestrate connections set-credentials -a oic_llm_creds --env live \
  -e "url_name=$GRANITE_ROUTE_URL"
  

# #######################################
# # Connections – Groq
# #######################################

orchestrate connections import \
  --file connections/groq_connections.yaml


 # Set credentials for draft an live environment
orchestrate connections set-credentials -a "groq_credentials" --env draft \
  -e "api_key=$GROQ_API_KEY"

orchestrate connections set-credentials -a "groq_credentials" --env live \
  -e "api_key=$GROQ_API_KEY"

# #######################################
# # Connections – Anthropic
# #######################################

orchestrate connections import \
  --file connections/claude_connections.yaml


 # Set credentials for draft an live environment
orchestrate connections set-credentials -a "anthropic_credentials" --env draft -e "api_key=$ANTHROPIC_API_KEY"


orchestrate connections set-credentials -a "anthropic_credentials" --env live -e "api_key=$ANTHROPIC_API_KEY"

# #######################################
# # Import Models
# #######################################

orchestrate models import \
  --file models/groq-openai.yaml \
  --app-id groq_credentials

orchestrate models import \
  --file models/anthropic-claude.yaml \
  --app-id anthropic_credentials

#######################################
# Import Tools
#######################################

cd tools

orchestrate tools import -k python -f cost_analysis_tool.py -r requirements.txt
orchestrate tools import -k python -f oic_granite_summary_tool.py -r requirements.txt --app-id oic_llm_creds

cd ..

#######################################
# Import Agents
#######################################

orchestrate agents import --file agents/oic_cost_inflation_analysis_agent.yaml --app-id 'anthropic_credentials'

orchestrate agents import --file agents/oic_cost_insights_supervisor_agent.yaml --app-id oic_llm_creds
