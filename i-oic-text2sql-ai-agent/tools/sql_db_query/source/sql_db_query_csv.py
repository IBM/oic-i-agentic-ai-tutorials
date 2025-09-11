from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
import pandas as pd
import pandasql
import traceback
import os

@tool(
    name="sql_db_query_csv",
    description=(
    "Input must be a SELECT SQL query using the 'df' table, which contains data from the orders.csv file. "
    "Only SELECT queries are supported. Columns available are: ID, PONumber, PurchaseOrderItem, etc."
    ),

    permission=ToolPermission.READ_ONLY
)
def sql_db_query(query: str) -> str:
    """
    Executes a SQL SELECT query on a CSV file using pandas.
    """
    #csv_path = "./orders.csv"  # Update this path as needed
    csv_path = os.path.join(os.path.dirname(__file__), "orders.csv")

    try:
        if not query.strip().lower().startswith("select"):
            return "Only SELECT queries are supported for CSV."

        # Load CSV into a DataFrame
        df = pd.read_csv(csv_path)

        # Use pandasql to run SQL queries on DataFrames
        
        pysqldf = lambda q: pandasql.sqldf(q, {"df": df})

        result_df = pysqldf(query)

        if result_df.empty:
            return "Query executed successfully. No rows returned."

        # Format the result
        result_lines = [" | ".join(result_df.columns), "-" * 40]
        for _, row in result_df.iterrows():
            result_lines.append(" | ".join(str(val) for val in row))

        return "\n".join(result_lines)

    except Exception:
        return f"Unexpected error:\n{traceback.format_exc()}"

# Example usage
if __name__ == "__main__":
    query = "SELECT * FROM df ORDER BY ID DESC LIMIT 5"
    result = sql_db_query(query)
    #print("Query executed successfully!")
    print(result)
