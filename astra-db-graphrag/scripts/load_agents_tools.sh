source .env

# Connections
orchestrate connections import -f wxo/connections/astradb.yaml
orchestrate connections import -f wxo/connections/watsonx.yaml

# Credentials
orchestrate connections set-credentials -a astradb --environment draft -e ASTRA_DB_API_ENDPOINT=$ASTRA_DB_API_ENDPOINT -e ASTRA_DB_APPLICATION_TOKEN=$ASTRA_DB_APPLICATION_TOKEN
orchestrate connections set-credentials -a watsonx --environment draft -e WATSONX_APIKEY=$WATSONX_APIKEY -e WATSONX_PROJECT_ID=$WATSONX_PROJECT_ID

# Tools
orchestrate tools import -k python -f wxo/tools/orchestrate_rag_tool.py --app-id astradb --app-id watsonx -r wxo/tools/requirements.txt
orchestrate tools import -k python -f wxo/tools/orchestrate_graph_rag_tool.py --app-id astradb --app-id watsonx -r wxo/tools/requirements.txt

# Agent
orchestrate agents import -f wxo/agents/orchestrate_docs_agent.yaml