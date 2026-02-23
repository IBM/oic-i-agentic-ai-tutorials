# Standard library imports
from typing import Any, Dict, Optional

# Third-party library imports
import requests

from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class SlackClient:
    """A remote client for Slack."""

    def __init__(self, base_url: str, bearer_token: str):
        """
        Args:
            base_url: The base URL for the Slack API (e.g., https://slack.com/api).
            bearer_token: The bearer token used for authentication fetched from WxO connection-manager.
        """
        self.base_url = base_url
        self.token = bearer_token

    def post_request(
        self,
        entity: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Sends a POST request to a Slack API entity.

        Args:
            entity: The Slack API method, e.g., 'chat.postMessage'.
            payload: A dictionary containing the input payload.
            headers: Optional HTTP headers.
            params: Optional query parameters.

        Returns:
            The JSON response from the Slack API.
        """
        url = f"{self.base_url}/{entity}"

        if headers is None:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }

        response = requests.post(url=url, json=payload, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_request(
        self,
        entity: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Sends a GET request to a Slack API entity.

        Args:
            entity: The Slack API method, e.g., 'users.list'.
            headers: Optional HTTP headers.
            params: Optional query parameters.

        Returns:
            The JSON response from the Slack API.
        """
        url = f"{self.base_url}/{entity}"

        if headers is None:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

        response = requests.get(url=url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()


def get_slack_client() -> SlackClient:
    """
    Get the slack client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the Slack client.
    """
    credentials = get_tool_credentials(Systems.SLACK)

    slack_client = SlackClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
    )
    return slack_client
