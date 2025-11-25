from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
import pandas as pd
import pandasql
import traceback
from io import StringIO

# -----------------------------
# Embedded CSV data
# -----------------------------
CSV_DATA = """service,region,plan,date,price,prev_price,inflation_pct,comment,sentiment,sentiment_score
Netflix,United States,Standard,2022-01,13.99,13.99,0.0,Great content library but getting expensive,Neutral,0
Netflix,United States,Standard,2023-01,15.49,13.99,10.72,Another price hike? Considering canceling,Negative,-1
Netflix,United States,Standard,2024-01,15.49,15.49,0.0,At least they didn't raise prices this year,Neutral,0
Netflix,United States,Standard,2025-01,17.99,15.49,16.14,"This is getting ridiculous, quality hasn't improved",Negative,-2
Disney+,United States,Premium,2022-01,7.99,7.99,0.0,Amazing value for families with kids!,Positive,2
Disney+,United States,Premium,2023-01,10.99,7.99,37.55,Huge jump but still cheaper than Netflix,Neutral,0
Disney+,United States,Premium,2024-01,13.99,10.99,27.3,Two big increases in two years feels unfair,Negative,-1
Disney+,United States,Premium,2025-01,15.99,13.99,14.3,Starting to match Netflix pricing now,Negative,-1
Spotify,United Kingdom,Premium,2022-01,9.99,9.99,0.0,"Best music service, worth every penny",Positive,2
Spotify,United Kingdom,Premium,2023-01,10.99,9.99,10.01,Small increase but understandable with inflation,Neutral,0
Spotify,United Kingdom,Premium,2024-01,11.99,10.99,9.1,Another year another hike,Neutral,0
Spotify,United Kingdom,Premium,2025-01,11.99,11.99,0.0,Happy they held pricing this year,Positive,1
Amazon Prime Video,India,Monthly,2022-01,179.0,179.0,0.0,"बहुत अच्छी सेवा, reasonable price",Positive,2
Amazon Prime Video,India,Monthly,2023-01,199.0,179.0,11.17,Price increase but still affordable,Neutral,0
Amazon Prime Video,India,Monthly,2024-01,299.0,199.0,50.25,Massive jump! This is too much,Negative,-2
Amazon Prime Video,India,Monthly,2025-01,299.0,299.0,0.0,At least stable now but expensive,Neutral,0
"""


@tool(
    name="cost_analysis_tool",
    description=(
        "Run SQL SELECT queries on an in-memory DataFrame called `prices` containing "
        "streaming price inflation data. Only SELECT queries are allowed."
    ),
    permission=ToolPermission.READ_ONLY
)
def sql_db_query_csv(query: str) -> str:
    try:
        if not query.strip().lower().startswith("select"):
            return "Only SELECT queries are supported."

        # Load CSV from embedded string
        df = pd.read_csv(StringIO(CSV_DATA))

        # Run SQL
        pysqldf = lambda q: pandasql.sqldf(q, {"prices": df, "df": df})
        result_df = pysqldf(query)

        if result_df.empty:
            return "Query executed successfully. No rows returned."

        # Format output as readable string
        lines = []
        for _, row in result_df.iterrows():
            line = (
                f"{row.get('date', '')}: {row.get('service', '')} "
                f"({row.get('region', '')}, {row.get('plan', '')}) - "
                f"Price: ${row.get('price', 0):.2f}, Previous: ${row.get('prev_price', 0):.2f}, "
                f"Inflation: {row.get('inflation_pct', 0):.2f}%, "
                f"Sentiment: {row.get('sentiment', '')} ({row.get('sentiment_score', 0)}), "
                f"Comment: {row.get('comment', '')}"
            )
            lines.append(line)

        return "\n".join(lines)

    except Exception as e:
        return f"Error executing query: {str(e)}\n{traceback.format_exc()}"


# For local debugging
if __name__ == "__main__":
    print(sql_db_query_csv("SELECT date, region, plan, price, prev_price, inflation_pct, sentiment, sentiment_score, comment FROM prices WHERE service='Disney+' AND sentiment='Negative' ORDER BY sentiment_score ASC LIMIT 3"))