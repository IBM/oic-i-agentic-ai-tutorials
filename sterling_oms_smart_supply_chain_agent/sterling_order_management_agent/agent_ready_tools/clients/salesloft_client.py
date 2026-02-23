from typing import Any, Optional

import requests

from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems

# TODO: Need to modify per team usage.
DEFAULT_SCOPES = [
    "accounts:delete",
    "accounts:read",
    "accounts:write",
    "opportunities:delete",
    "opportunities:read",
    "opportunities:write",
    "people:delete",
    "people:read",
    "people:write",
    "crm:read",
    "external_id:delete",
    "external_id:read",
    "external_id:write",
    "external_id_configuration:delete",
    "external_id_configuration:read",
    "external_id_configuration:write",
    "activities:read",
    "activities:write",
    "calls:read",
    "calls:write",
    "conversations:read",
    "conversations:write",
    "dialer_recordings:read",
    "emails:read",
    "emails:write",
    "meetings:read",
    "meetings:write",
    "notifications:write",
    "audit_reports:read",
    "audit_reports:write",
    "groups:write",
    "team:delete",
    "team:read",
    "team:write",
    "cadences:delete",
    "cadences:read",
    "cadences:write",
    "notes:delete",
    "notes:read",
    "notes:write",
    "signal_registrations:delete",
    "signal_registrations:read",
    "signal_registrations:write",
    "signals:write",
    "tasks:delete",
    "tasks:read",
    "tasks:write",
    "workflow:delete",
    "workflow:read",
    "workflow:write",
]


class SalesloftClient:
    """A remote client for Salesloft."""

    def __init__(
        self,
        base_url: str,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: Optional[list[str]] = None,
    ):
        """
        Args:
            base_url: The base URL for the Salesloft API.
            token_url: The URL for access tokens for the Salesloft API.
            client_id: The client id to authenticate with.
            client_secret: The client secret to authenticate with.
            scope: A string of scopes separated by space, which is used to get token for API requests in Salesloft.
        """
        self.base_url = base_url
        self.token_url = token_url
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        self.client_id = client_id
        self.client_secret = client_secret
        self.bearer_token = self.get_salesloft_oauth_token(
            scope=DEFAULT_SCOPES if scope is None else scope
        )
        assert self.bearer_token

    def get_request(
        self,
        version: str,
        endpoint: str,
        path_parameter: Optional[str] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Executes a GET request against Salesloft API.

        Args:
            version: The version of API.
            endpoint: The specific endpoint to make the request against, like "accounts".
            path_parameter: The path parameter for the REST API.
            data: The request payload data.

        Returns:
            The JSON response from the Salesloft API.
        """

        get_headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Accept": self.headers["Accept"],
        }
        if path_parameter:
            url = f"{self.base_url}/{version}/{endpoint}/{path_parameter}"
        else:
            url = f"{self.base_url}/{version}/{endpoint}"
        try:
            response = requests.get(url, headers=get_headers, data=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError:
            # We still want to return the json blob of the HTTP error message to the tool code
            # This is so that we can output the error message on the agent UI
            try:
                return response.json()
            except ValueError:
                # Handle the case where response content is not JSON
                return {
                    "errors": {
                        "errorMessage": "Non-JSON response",
                        "status_code": response.status_code,
                    }
                }

    def post_request(
        self,
        version: str,
        endpoint: str,
        data: dict,
    ) -> dict[str, Any]:
        """
        Executes a POST request against a Salesloft API.

        Args:
            version: The version of API.
            endpoint: The specific endpoint to make the request against, like "accounts".
            data: The input data request.

        Returns:
            The JSON response from the Salesloft REST API.
        """
        post_headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Accept": self.headers["Accept"],
            "Content-Type": "multipart/form-data",
        }
        url = f"{self.base_url}/{version}/{endpoint}"
        try:
            response = requests.post(url, headers=post_headers, data=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError:
            # We still want to return the json blob of the HTTP error message to the tool code
            # This is so that we can output the error message on the agent UI
            try:
                return response.json()
            except ValueError:
                # Handle the case where response content is not JSON
                return {
                    "errors": {
                        "errorMessage": "Non-JSON response",
                        "status_code": response.status_code,
                    }
                }

    def put_request(
        self,
        version: str,
        endpoint: str,
        path_parameter: str,
        data: dict,
    ) -> dict[str, Any]:
        """
        Executes a PUT request against a Salesloft API.

        Args:
            version: The version of API.
            endpoint: The specific endpoint to make the request against, like "accounts".
            path_parameter: The path parameter for the REST API.
            data: The input data request.

        Returns:
            The JSON response from the Salesloft REST API.
        """
        put_headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Accept": self.headers["Accept"],
            "Content-Type": "multipart/form-data",
        }
        try:
            url = f"{self.base_url}/{version}/{endpoint}/{path_parameter}"
            response = requests.put(url, headers=put_headers, data=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError:
            # We still want to return the json blob of the HTTP error message to the tool code
            # This is so that we can output the error message on the agent UI
            try:
                return response.json()
            except ValueError:
                # Handle the case where response content is not JSON
                return {
                    "errors": {
                        "errorMessage": "Non-JSON response",
                        "status_code": response.status_code,
                    }
                }

    def delete_request(
        self,
        version: str,
        endpoint: str,
        path_parameter: str,
        data: Optional[dict[str, Any]] = None,
    ) -> int:
        """
        Executes a DELETE request against a Salesloft API.

        Args:
            version: The version of API.
            endpoint: The specific endpoint to make the request against, like "accounts".
            path_parameter: The path parameter for the REST API.
            data: The input data request.

        Returns:
            The status code responded from the Salesloft REST API.
        """
        delete_headers = {
            "Authorization": f"Bearer {self.bearer_token}",
        }
        url = f"{self.base_url}/{version}/{endpoint}/{path_parameter}"
        response = requests.delete(url, headers=delete_headers, data=data)
        response.raise_for_status()
        return response.status_code

    def get_salesloft_oauth_token(self, scope: Optional[list[str]] = None) -> str:
        """
        Args:
            scope: A list of scopes which is used to get token for API requests in Salesloft.

        Returns:
            An access token for the specific scope(s).
        """
        # Set default scope if none is given
        scopes_to_use = scope if scope is not None else DEFAULT_SCOPES

        # Prepare the request data
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": " ".join(scopes_to_use),
        }

        # Make the POST request to get the access token.
        response = requests.post(self.token_url, headers=self.headers, data=data)

        response.raise_for_status()

        access_token = ""

        # Check if the request was successful
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data["access_token"]

        return access_token


def get_salesloft_client(scope: Optional[list[str]] = None) -> SalesloftClient:
    """
    Get the Salesloft client with credentials.

    Args:
        scope: A list of scopes which is used to get token for API requests in Salesloft.

    Returns:
        A new instance of the Salesloft client.
    """
    credentials = get_tool_credentials(Systems.SALESLOFT)
    salesloft_client = SalesloftClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        token_url=credentials[CredentialKeys.TOKEN_URL],
        client_id=credentials[CredentialKeys.CLIENT_ID],
        client_secret=credentials[CredentialKeys.CLIENT_SECRET],
        scope=scope,
    )
    return salesloft_client
