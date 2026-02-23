from http import HTTPMethod
from typing import Any, Dict, Optional, Union

import requests

from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    handling_exceptions,
)
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class DropboxClient:
    """A remote client for Dropbox."""

    def __init__(self, base_url: str, bearer_token: str, version: str = "2"):
        """
        Args:
            base_url: The base URL for the Dropbox API.
            bearer_token: The bearer token from wxo connections-manager.
            version: The version of Dropbox API.
        """
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}",
        }
        self.version = version

    def delete_request(
        self,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> int | ErrorDetails:
        """
        Executes a DELETE-like POST request against Dropbox (Dropbox uses POST for delete).

        Args:
            endpoint: The Dropbox API endpoint (e.g., "files/delete_v2").
            payload: The request payload.

        Returns:
            HTTP status code or the API request error details if an error occurs during the API call.
        """
        url = f"{self.base_url}/{self.version}/{endpoint}"
        response: requests.Response | None = None
        try:
            response = requests.request(
                HTTPMethod.POST,
                url=url,
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            return response.status_code
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def post_request(
        self,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any] | ErrorDetails:
        """
        Executes a POST request against Dropbox API.

        Args:
            endpoint: The Dropbox API endpoint (e.g., "files/create_folder_v2").
            payload: The request payload.

        Returns:
            JSON response from Dropbox or the API request error details if an error occurs during the API call.
        """
        url = f"{self.base_url}/{self.version}/{endpoint}"
        response: requests.Response | None = None
        try:
            response = requests.request(
                method=HTTPMethod.POST,
                url=url,
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            json_response = response.json()
            return json_response
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def upload_request(
        self,
        endpoint: str,
        payload: Optional[Union[Dict[str, Any], bytes, bytearray]] = None,
    ) -> Dict[str, Any] | ErrorDetails:
        """
        Executes a POST request against Dropbox API.

        Args:
            endpoint: The Dropbox API endpoint (e.g., "files/create_folder_v2").
            payload: The request payload (sent as JSON).

        Returns:
            JSON response from Dropbox or the API request error details if an error occurs during the API call.
        """
        url = f"https://content.dropboxapi.com/{self.version}/{endpoint}"
        response: requests.Response | None = None
        try:
            response = requests.request(
                HTTPMethod.POST,
                url=url,
                data=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            json_response = response.json()
            return json_response
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def download_request(
        self, endpoint: str, custom_headers: Dict[str, str]
    ) -> bytes | ErrorDetails:
        """Executes a POST request to download a file from Dropbox using re-auth logic."""
        url = f"https://content.dropboxapi.com/{self.version}/{endpoint}"
        response: requests.Response | None = None
        try:
            response = requests.request(
                HTTPMethod.POST,
                url=url,
                headers=self.headers | custom_headers,
            )
            response.raise_for_status()
            return response.content
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)


def get_dropbox_client() -> DropboxClient | ErrorDetails:
    """
    Get the Dropbox client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the Dropbox client or the error details object if an error occurs while initializing the client and its credentials.
    """
    try:
        credentials = get_tool_credentials(Systems.DROPBOX)
        dropbox_client = DropboxClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
        )
    except (AssertionError, ValueError, requests.exceptions.RequestException) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Dropbox client initialization:{str(e)}",
            details=f"Caught error during Dropbox client initialization:{str(e)}",
            recommendation=None,
        )
    return dropbox_client
