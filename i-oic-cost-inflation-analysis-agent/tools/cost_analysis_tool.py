from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
import pandas as pd
import pandasql
import traceback
import os

@tool(
    name="cost_analysis_tool",
    description=(
        "Run SQL SELECT queries on the 'df' table, which is loaded from "
        "streaming_cost_inflation.csv. Only SELECT queries are allowed. "
        "Useful for reasoning on streaming platform price inflation. "
        "The table is exposed as 'df' and contains all columns from the CSV."
    ),
    permission=ToolPermission.READ_ONLY
)
def getCostAnalytics(query: str) -> str:
    """
    Executes a SQL SELECT query on a CSV file using pandas + pandasql.
    """

    # Resolve CSV path relative to this script (safe for agent packaging)
    csv_path = os.path.join(os.path.dirname(__file__), "streaming_cost_inflation.csv")

    try:
        # Validate SQL
        cleaned = query.strip().lower()
        if not cleaned.startswith("select"):
            return ("❌ Only SELECT statements are supported. "
                    "Example: SELECT * FROM df LIMIT 5")

        # Load CSV
        if not os.path.exists(csv_path):
            return f"❌ CSV file not found at: {csv_path}"

        df = pd.read_csv(csv_path)

        # Make df available for SQL engine
        pysqldf = lambda q: pandasql.sqldf(q, {"df": df})

        # Execute query
        result_df = pysqldf(query)

        # No rows
        if result_df.empty:
            return "Query executed successfully — no rows matched."

        # Format output
        col_line = " | ".join(result_df.columns)
        separator = "-" * len(col_line)

        rows = []
        for _, row in result_df.iterrows():
            rows.append(" | ".join(str(val) for val in row))

        return f"{col_line}\n{separator}\n" + "\n".join(rows)

    except Exception:
        return f"Unexpected error:\n{traceback.format_exc()}"


# Example usage
if __name__ == "__main__":
    query = "SELECT * FROM df LIMIT 5"
    result = sql_db_query_csv(query)
    print(result)
