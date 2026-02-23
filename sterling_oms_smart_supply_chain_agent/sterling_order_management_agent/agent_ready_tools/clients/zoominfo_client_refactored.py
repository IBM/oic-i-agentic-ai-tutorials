import json
from typing import Any, Optional

import requests

from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    handling_exceptions,
    no_data_in_get_request,
)
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class ZoominfoClient:
    """A remote client for Zoominfo."""

    def __init__(self, base_url: str, token_url: str, username: str, password: str):
        """
        Args:
            base_url: The base URL for the Zoominfo API.
            token_url: The URL to get access tokens for the Zoominfo API.
            username: The Zoominfo account username (email address).
            password: The Zoominfo account password.
        """
        self.base_url = base_url
        self.token_url = token_url
        self.username = username
        self.password = password
        self.headers = {"Content-Type": "application/json"}
        self.access_token = self.get_zoominfo_access_token()
        assert isinstance(self.access_token, str)  # to ensure it is not ErrorDetails

    def post_request(
        self,
        category: str,
        endpoint: str,
        data: dict,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a POST request against a Zoominfo API.

        Args:
            category: The specific category of the API, like "search", "enrich".
            endpoint: The specific endpoint of the API, like "contact", "company".
            data: The input data request.

        Returns:
            The JSON response from the Zoominfo API or the API request error details if an error occurs during the API call.
        """
        post_headers = {
            "Content-Type": self.headers["Content-Type"],
            "Authorization": f"Bearer {self.access_token}",
        }
        url = f"{self.base_url}/{category}/{endpoint}"
        payload = json.dumps(data)
        response: requests.Response | None = None
        try:
            response = requests.post(url, headers=post_headers, data=payload)
            response.raise_for_status()
            json_response = response.json()
            return json_response
        except (
            requests.exceptions.RequestException,
            json.JSONDecodeError,
            requests.HTTPError,
        ) as e:
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=self.token_url)

    def get_request(
        self,
        endpoint: str,
        data: Optional[dict[str, Any]] = None,
        search_key: Optional[str] = None,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a GET request against a Zoominfo API.

        Args:
            endpoint: The specific endpoint of the API, like "lookup/inputfields/contact/search".
            data: The input data request.
            search_key: The field in the API response that should be checked for the presence of data.

        Returns:
            The JSON response from the Zoominfo API or the API request error details if an error occurs during the API call.
        """
        get_headers = {
            "Authorization": f"Bearer {self.access_token}",
        }
        url = f"{self.base_url}/{endpoint}"
        response: requests.Response | None = None
        try:
            response = requests.get(url, headers=get_headers, data=data)
            response.raise_for_status()
            json_response = response.json()
            # currently no tool uses the get_request method, no_data_in_get_request condition can be modified in future if needed
            if search_key and not json_response.get(search_key, None):
                return no_data_in_get_request(response=response)
            return json_response
        except (
            requests.exceptions.RequestException,
            json.JSONDecodeError,
            requests.HTTPError,
        ) as e:
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=self.token_url)

    def get_zoominfo_access_token(self) -> str | ErrorDetails:
        """
        Returns:
            An access (JWT) token  or the API request error details if an error occurs during the API call.
        """
        # Prepare the request payload data
        payload = json.dumps(
            {
                "username": self.username,
                "password": self.password,
            }
        )
        response: requests.Response | None = None
        try:
            # Make the POST request to get the access token
            response = requests.post(self.token_url, headers=self.headers, data=payload)

            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=self.token_url)

        access_token = ""

        # Check if the request was successful
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data["jwt"]

        return access_token


def get_zoominfo_client() -> ZoominfoClient | ErrorDetails:
    """
    Get the Zoominfo client with credentials.

    Returns:
        A new instance of the Zoominfo client or the error details if an error occurs during creating new instance of the Zoominfo client.
    """
    try:
        credentials = get_tool_credentials(Systems.ZOOMINFO)
        zoominfo_client = ZoominfoClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            token_url=credentials[CredentialKeys.TOKEN_URL],
            username=credentials[CredentialKeys.USERNAME],
            password=credentials[CredentialKeys.PASSWORD],
        )
    except (
        AssertionError,
        ValueError,
        KeyError,
        AttributeError,
        requests.exceptions.RequestException,
    ) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Zoominfo client initialization:{str(e)}",
            details=f"Caught error during Zoominfo client initialization:{str(e)}",
            recommendation=None,
        )
    return zoominfo_client
