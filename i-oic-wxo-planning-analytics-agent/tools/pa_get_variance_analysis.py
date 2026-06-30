from typing import Optional, List, Dict, Any
import logging
import pandas as pd
from TM1py.Services import TM1Service
from TM1py.Exceptions import TM1pyRestException
from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType
from ibm_watsonx_orchestrate.run import connections
from orchestrate import tool 


MY_APP_ID=”planning-analytics-test”


@tool({"app_id": MY_APP_ID, "type": ConnectionType. KEY_VALUE
})
def pa_get_variance_analysis(
    measure: str = "Revenue",
    version_actual: str = "Actual",
    version_budget: str = "Budget",
    time_subset: str = "All Months",
    cube_name: str = "FinanceCube",
    limit: int = 12
) -> str:
    """
    Retrieve and calculate variance analysis from IBM Planning Analytics using TM1py.

    Parameters
    ----------
    measure : str
        The measure to analyze (e.g., 'Revenue').
    version_actual : str
        The name of the actual version.
    version_budget : str
        The name of the budget version.
    time_subset : str
        The name of the public subset in the Time dimension.
    cube_name : str
        The name of the cube to query.
    limit : int
        The maximum number of time periods to return. Defaults to 12.

    Returns
    -------
    Optional [List[Dict[str, Any]]]
        A list of dictionaries with time period, actual, budget, and variance values.
    """
    try:
        # MDX query to fetch actual and budget data
        mdx = f"""
        SELECT 
            {{
                [Version].[{version_actual}].[{measure}],
                [Version].[{version_budget}].[{measure}]
            }} ON COLUMNS,
            TM1SubsetToSet([Time].[Time], "{time_subset}", "public") ON ROWS
        FROM [{cube_name}]
        """
        
creds = connections.key_value(MY_APP_ID)
        credentials = {
            "address": creds.get('address'),
            "user": creds.get('user'),
            "password": creds.get('password'),
            "port": creds.get('port'),
            "ssl": True,
        }


        with TM1Service(session_context="Orchestrate:get_variance_data", **credentials) as tm1:
            df = tm1.cubes.cells.execute_mdx_dataframe_shaped(mdx=mdx, display_attribute=True)

        # Rename columns for clarity
        df.rename(columns={
            f"{version_actual}.{measure}": "Actual",
            f"{version_budget}.{measure}": "Budget"
        }, inplace=True)

        # Calculate variance
        df["Actual"] = pd.to_numeric(df["Actual"], errors="coerce")
        df["Budget"] = pd.to_numeric(df["Budget"], errors="coerce")
        df["Variance"] = df["Actual"] - df["Budget"]

        # Clean and sort
        df.fillna("Missing Data", inplace=True)
        df_sorted = df.sort_index().head(limit)

        # Format output
        result = df_sorted.reset_index().rename(columns={"Time": "Period"}).to_dict(orient="records")
        return result

    except TM1pyRestException as tm1_error:
        logging.error("TM1 REST API error: %s", tm1_error)
    except Exception as general_error:
        logging.error("Unexpected error: %s", general_error)

    return None