set -e

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