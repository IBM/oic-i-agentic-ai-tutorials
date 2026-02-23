from typing import Any, Dict, Optional

import requests

from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    handling_exceptions,
)
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
    ) -> Dict[str, Any] | ErrorDetails:
        """
        Sends a POST request to a Slack API entity.

        Args:
            entity: The Slack API method, e.g., 'chat.postMessage'.
            payload: A dictionary containing the input payload.
            headers: Optional HTTP headers.
            params: Optional query parameters.

        Returns:
            The JSON response from the Slack API or the API request error details if an error occurs during the API call.
        """
        url = f"{self.base_url}/{entity}"

        if headers is None:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }

        response: requests.Response | None = None
        try:
            response = requests.post(url=url, json=payload, headers=headers, params=params)
            response.raise_for_status()
            json_response = response.json()
            return json_response
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def get_request(
        self,
        entity: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any] | ErrorDetails:
        """
        Sends a GET request to a Slack API entity.

        Args:
            entity: The Slack API method, e.g., 'users.list'.
            headers: Optional HTTP headers.
            params: Optional query parameters.

        Returns:
            The JSON response from the Slack API or the API request error details if an error occurs during the API call.
        """
        url = f"{self.base_url}/{entity}"

        if headers is None:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

        response: requests.Response | None = None
        try:
            response = requests.get(url=url, headers=headers, params=params)
            response.raise_for_status()
            json_response = response.json()
            return json_response
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)


def get_slack_client() -> SlackClient | ErrorDetails:
    """
    Get the slack client with credentials or the error details if an error occurs during creating
    new instance of the Slack client.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the Slack client or the error details if an error occurs during creating new instance of the Slack client.
    """
    try:
        credentials = get_tool_credentials(Systems.SLACK)
        slack_client = SlackClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
        )
    except (AssertionError, ValueError, requests.exceptions.RequestException) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Slack client initialization:{str(e)}",
            details=f"Caught error during Slack client initialization:{str(e)}",
            recommendation=None,
        )
    return slack_client
