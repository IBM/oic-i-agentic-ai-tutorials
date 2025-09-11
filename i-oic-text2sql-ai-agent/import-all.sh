set -e

orchestrate connections add -a openai_creds

orchestrate connections configure -a openai_creds --env draft -k key_value -t team

orchestrate connections set-credentials -a openai_creds --env draft -e "api_key=YOUR_API_KEY"

orchestrate models import --file models/openai-gpt-4o-mini.yaml --app-id openai_creds

#Ensure pandas is installed at the same python location which orchestrate is using
$(head -n 1 $(which orchestrate) | cut -c 3-) -m pip install pandas pandasql


orchestrate tools import \
    -k python \
    -f "tools/sql_db_query/source/sql_db_query.py" \
    -p "tools/sql_db_query" \
    -r "tools/sql_db_query/source/requirements.txt"

orchestrate tools import \
    -k python \
    -f "tools/sql_db_query/source/sql_db_query_csv.py" \
    -p "tools/sql_db_query" \
    -r "tools/sql_db_query/source/requirements.txt"

orchestrate agents import -f "agents/agent.yaml"



