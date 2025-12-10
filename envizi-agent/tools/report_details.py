from ibm_watsonx_orchestrate.agent_builder.tools import tool
# Connection setup
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from ibm_watsonx_orchestrate.run import connections
from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType, ExpectedCredentials
import requests
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


ENVIZI_BASE_URL = "https://usapi.envizi.com/api"
ENVIZI_APP_ID = 'envizi_api_connection'


@tool(
    name="report_details",
    description="Fetches the esg reports details from Envizi API",
    permission=ToolPermission.READ_ONLY,
    expected_credentials=[ExpectedCredentials(
        app_id = ENVIZI_APP_ID,
        type = ConnectionType.BEARER_TOKEN
    )]
)
def report_details(report_name : str):
    """
    Collect the report details from ESG reporting system(Envizi API)
    args: 
        report_name (str) : The report name of the ESG reports
    Returns:
        dict: A dictionary containing the report details
    """

    try:

        # Get the ap endpoint using wxo connection
        conn = connections.bearer_token(ENVIZI_APP_ID)
        # This can be used for authentication in envizi platform
        headers = {
        'Authorization': f"Bearer {str(conn.token)}",
        'Content-Type': 'application/json'
        }

        # Custom logic or external API call
        response = requests.get(f"{ENVIZI_BASE_URL}/data/{report_name}", headers=headers)
        original = response.json()
        return original[:1]
        # if response.status_code == 200:
        #     original = response.json()
        #     return original[:1]
        # else:
            
        #     # fetch data from current job entries
        #     return {"error": "Unable to find the reports"}
            
    except Exception as ex:
        return {"Error": f"Something went wrong{ex}"}
