orchestrate env add --name oictutorial --url https://api.eu-central-1.dl.watson-orchestrate.ibm.com/instances/20250508-1435-1457-50e0-b8f069e11f66

orchestrate env activate oictutorial --api-key azE6dXNyX2NkN2VlM2MzLWNlMDktM2Q3ZC1hN2U3LWRlNzdjNGJmYWQ1NzpVbjUzMXB2bnY2bVA4VUZUVHROZzJmNXNuRGgvdWdRVGlIWU0vWGE2NjZrPToxZVNY

## Create Connections 

orchestrate connections add -a groq_credentials
orchestrate connections configure -a groq_credentials --env draft -k key_value -t team
orchestrate connections set-credentials -a groq_credentials --env draft -e "api_key=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"

orchestrate connections configure -a groq_credentials --env live -k key_value -t team
orchestrate connections set-credentials -a groq_credentials --env live -e "api_key=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"



orchestrate connections add -a anthropic_credentials
orchestrate connections configure -a anthropic_credentials --env draft -k key_value -t team
orchestrate connections set-credentials -a anthropic_credentials --env draft -e "api_key=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"

orchestrate connections configure -a anthropic_credentials --env team -k key_value -t team
orchestrate connections set-credentials -a anthropic_credentials --env team -e "api_key=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"

## Import Models 

orchestrate models import --file groq-openai.yaml --app-id groq_credentials

orchestrate models import --file anthropic-claude.yaml --app-id anthropic_credentials

## Import Tools 

orchestrate tools import -k python -f oic_granite_summary_tool.py -r requirements.txt

## Import Agents

orchestrate agents import --file oic_cost_inflation_analysis_agent.yaml 

orchestrate agents import --file oic_cost_insights_master_agent.yaml



