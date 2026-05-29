import json
import os
import requests

from ibm_watsonx_orchestrate.agent_builder.tools import ToolPermission, tool
from ibm_watsonx_orchestrate.run import connections
from ibm_watsonx_orchestrate.client.connections import ConnectionType
from ibm_watsonx_orchestrate.run.context import AgentRun


@tool(
    name="profile",
    permission=ToolPermission.READ_WRITE
)
def profile(context: AgentRun) -> dict:
    """
    Get profile details

    Args:
        context: context of Agent run

    Returns:
        Dictionary with user profile details
    """

    # Extract runtime context variables from the agent run, such as user_id.
    req_context = context.request_context
    user_id = str(req_context.get('user_id'))

    if not user_id or not user_id.strip():
        return {"error": "User ID is required"}

    # Calling  endpoint
    try:

        # Update this URL to your actual profile service endpoint before using the tool.
        profile_url = f"https://test-function.21gqgfig993a.us-south.codeengine.appdomain.cloud/data?user_id={user_id}"
        
        ## update below code to call endpoint
        response = requests.get(profile_url)
        response.raise_for_status()
        return response.json()

    except Exception as e:
        error_message = f"Unexpected error: {str(e)}"
        return {"error": error_message}