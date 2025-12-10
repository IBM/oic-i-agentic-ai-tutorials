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
    name="list_esg_reports",
    description="Fetches the esg reports using Envizi API",
    permission=ToolPermission.READ_ONLY,
    expected_credentials=[ExpectedCredentials(
        app_id = ENVIZI_APP_ID,
        type = ConnectionType.BEARER_TOKEN
    )]
)
def list_esg_reports():
    """
    This is to list all the jobs ids from cos or current job list
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
        response = requests.get(f"{ENVIZI_BASE_URL}/meta/reports", headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            
            # fetch data from current job entries
            return {"error": "Unable to find the reports"}
            
    except Exception as ex:
        return {"Error": f"Something went wrong{ex}"}
