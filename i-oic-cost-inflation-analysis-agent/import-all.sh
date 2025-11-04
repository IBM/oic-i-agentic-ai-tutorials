set -e

orchestrate env add --name oictutorial --url <WXO Instance URL>

orchestrate env activate oictutorial --api-key <your api api_key>

## Create Connections 

### Groq Credentials

orchestrate connections add -a groq_credentials
orchestrate connections configure -a groq_credentials --env draft -k key_value -t team
orchestrate connections set-credentials -a groq_credentials --env draft -e "api_key=grok-api-key"

orchestrate connections configure -a groq_credentials --env live -k key_value -t team
orchestrate connections set-credentials -a groq_credentials --env live -e "api_key=grok-api-key"

### Anthropic Credentials

orchestrate connections add -a anthropic_credentials
orchestrate connections configure -a anthropic_credentials --env draft -k key_value -t team
orchestrate connections set-credentials -a anthropic_credentials --env draft -e "api_key=anthropic_api_key"

orchestrate connections configure -a anthropic_credentials --env team -k key_value -t team
orchestrate connections set-credentials -a anthropic_credentials --env team -e "api_key=anthropic_api_key"

## Import Models 

orchestrate models import --file groq-openai.yaml --app-id groq_credentials

orchestrate models import --file anthropic-claude.yaml --app-id anthropic_credentials

## Import Knowledge Base

orchestrate knowledge-bases import -f knowledge-bases/knowledge-base.yaml

## Import Tools 

orchestrate tools import -k python -f tools/oic_granite_summary_tool.py -r requirements.txt

## Import Agents

orchestrate agents import --file agents/oic_cost_inflation_analysis_agent.yaml 

orchestrate agents import --file agents/oic_cost_insights_master_agent.yaml



