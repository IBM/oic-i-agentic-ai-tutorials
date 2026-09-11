#!/usr/bin/env bash
set -x
source .env

source venv/bin/activate

orchestrate env activate apple-siri --apikey="$IBM_APIKEY"

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

orchestrate connections remove --app-id github_connection
orchestrate connections remove --app-id email_connection

orchestrate connections add --app-id github_connection
orchestrate connections add --app-id email_connection

orchestrate connections configure --app-id email_connection --environment live --type team --app-id email_connection --kind key_value
orchestrate connections configure --app-id github_connection --environment live  --type team --app-id github_connection --kind key_value

orchestrate connections set-credentials -a email_connection --env live -e "email_token=${EMAIL_TOKEN}"
orchestrate connections set-credentials -a github_connection --env live -e "github_token=${GITHUB_TOKEN}"

# Import all tools
for tool in email_expert.py financial_expert.py github_expert.py python_expert.py web_search_expert.py ; do
  orchestrate tools import -k python \
    -f "${SCRIPT_DIR}/tools/${tool}" \
    -r "${SCRIPT_DIR}/requirements.txt" \
    -p "${SCRIPT_DIR}/tools"
done


# ---------------------------
# Import Knowledge Base (PDF)
# ---------------------------
orchestrate knowledge-bases import -f "${SCRIPT_DIR}/tools/data/ibm-financial-investor-report.yaml"


# Import agents
for agent in email_agent.yaml financial_agent.yaml github_agent.yaml python_agent.yaml web_search_agent.yaml combined_global_agent.yaml; do
  orchestrate agents import -f "${SCRIPT_DIR}/agents/${agent}"
done


