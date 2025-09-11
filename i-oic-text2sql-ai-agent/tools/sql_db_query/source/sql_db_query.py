from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
import sqlite3
import traceback
import base64
import os

@tool(
    name="sql_db_query", 
    description="Input to this tool is a detailed and correct SQL query, output is a result from the database. If the query is not correct, an error message will be returned. If an error is returned, rewrite the query, check the query, and try again. If you encounter an issue with Unknown column 'xxxx' in 'field list', use sql_db_schema to query the correct table fields.", 
    permission=ToolPermission.READ_ONLY
)
def sql_db_query(query: str) -> str:
    """
    Executes a SQL query and returns the result or a natural language error message.
    Always call sql_db_query_checker before this.
    """
    db_path = "../resources/purchase_orders.db"
     # Resolve DB path relative to this script’s directory

    try:
        allowed = ("select", "insert", "update", "delete", "with")
        if not query.strip().lower().startswith(allowed):
            return "Only SELECT, INSERT, UPDATE, DELETE, and WITH queries are supported."

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query)
        print(cursor)
        if query.strip().lower().startswith("select"):
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            if not rows:
                return "Query executed successfully. No rows returned."
            result_lines = [" | ".join(columns), "-" * 40]
            for row in rows:
                result_lines.append(" | ".join(str(val) if val is not None else "" for val in row))
            return "\n".join(result_lines)
        else:
            conn.commit()
            return "Query executed successfully."
    except sqlite3.OperationalError as e:
        return f"SQL error: {str(e)}"
    except Exception as e:
        return f"Unexpected error:\n{traceback.format_exc()}"
    finally:
        conn.close()

# Example usage
if __name__ == "__main__":
    query = "SELECT * FROM 'ORDER' LIMIT 0,30"
    result = sql_db_query(query)
    #print("Query executed successfully!")
    print(result)