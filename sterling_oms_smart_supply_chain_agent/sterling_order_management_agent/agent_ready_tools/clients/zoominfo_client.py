import json
from typing import Any, Optional

import requests

from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class ZoominfoClient:
    """A remote client for Zoominfo."""

    def __init__(self, base_url: str, token_url: str, username: str, password: str):
        """
        Args:
            base_url: The base URL for the Zoominfo API.
            token_url: The URL to get access tokens for the Zoominfo API.
            username: The Zoominfo account uername (email address).
            password: The Zoominfo account password.
        """
        self.base_url = base_url
        self.token_url = token_url
        self.username = username
        self.password = password
        self.headers = {"Content-Type": "application/json"}
        self.access_token = self.get_zoominfo_access_token()
        assert self.access_token

    def post_request(
        self,
        category: str,
        endpoint: str,
        data: dict,
    ) -> dict[str, Any]:
        """
        Executes a POST request against a Zoominfo API.

        Args:
            category: The specific category of the API, like "search", "enrich".
            endpoint: The specific endpoint of the API, like "contact", "company".
            data: The input data request.

        Returns:
            The JSON response from the Zoominfo API.
        """
        post_headers = {
            "Content-Type": self.headers["Content-Type"],
            "Authorization": f"Bearer {self.access_token}",
        }
        url = f"{self.base_url}/{category}/{endpoint}"
        payload = json.dumps(data)
        response = requests.post(url, headers=post_headers, data=payload)
        # not raise http error as we want to get the error json blob.
        return response.json()

    def get_request(
        self,
        endpoint: str,
        data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Executes a GET request against a Zoominfo API.

        Args:
            endpoint: The specific endpoint of the API, like "lookup/inputfields/contact/search".
            data: The input data request.

        Returns:
            The JSON response from the Zoominfo API.
        """
        get_headers = {
            "Authorization": f"Bearer {self.access_token}",
        }
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, headers=get_headers, data=data)
        response.raise_for_status()
        return response.json()

    def get_zoominfo_access_token(self) -> str:
        """
        Returns:
            An access (JWT) token.
        """
        # Prepare the request payload data
        payload = json.dumps(
            {
                "username": self.username,
                "password": self.password,
            }
        )

        # Make the POST request to get the access token
        response = requests.post(self.token_url, headers=self.headers, data=payload)

        response.raise_for_status()

        access_token = ""

        # Check if the request was successful
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data["jwt"]

        return access_token


def get_zoominfo_client() -> ZoominfoClient:
    """
    Get the Zoominfo client with credentials.

    Returns:
        A new instance of the Zoominfo client.
    """
    credentials = get_tool_credentials(Systems.ZOOMINFO)
    zoominfo_client = ZoominfoClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        token_url=credentials[CredentialKeys.TOKEN_URL],
        username=credentials[CredentialKeys.USERNAME],
        password=credentials[CredentialKeys.PASSWORD],
    )
    return zoominfo_client
