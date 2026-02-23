from typing import Any, Dict, Optional

import requests

from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    handling_exceptions,
)
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems

T = Dict[str, Any] | ErrorDetails


class IBMTargetProcessClient:
    """A remote client for IBM Targetprocess."""

    def __init__(
        self,
        base_url: str,
        access_token: str,
        version: str = "v1",
    ):
        """
        Args:
            base_url: The base URL for the IBM Targetprocess API (e.g., https://your-domain.tpondemand.com).
            access_token: The access token used for authentication.
            version: The version of IBM Targetprocess API.
        """
        self.base_url = base_url
        self.version = version
        self.headers = {
            "Accept": "application/json",
        }
        self.access_token = access_token

    def get_request(
        self, entity: str, params: Optional[Dict[str, Any]] = None, full_path: bool = False
    ) -> T:
        """Sends a GET request to a IBM Targetprocess API entity."""
        url = (
            f"{self.base_url}/{entity}?access_token={self.access_token}"
            if full_path
            else f"{self.base_url}/api/{self.version}/{entity}?access_token={self.access_token}"
        )
        response = None
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def post_request(
        self,
        entity: str,
        payload: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None,
    ) -> T:
        """Sends a POST request to a IBM Targetprocess API entity."""
        url = f"{self.base_url}/api/{self.version}/{entity}?access_token={self.access_token}"
        response = None
        try:
            response = requests.post(url, json=payload, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def put_request(
        self,
        entity: str,
        payload: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None,
    ) -> T:
        """Sends a PUT request to update a IBM Targetprocess entity."""
        url = f"{self.base_url}/api/{self.version}/{entity}?access_token={self.access_token}"
        response = None
        try:
            response = requests.put(url, json=payload, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def delete_request(
        self,
        entity: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> T:
        """Sends a DELETE request to remove a Targetprocess entity."""
        url = f"{self.base_url}/api/{self.version}/{entity}?access_token={self.access_token}"
        response = None
        try:
            response = requests.delete(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)


def get_ibm_targetprocess_client(version: Optional[str] = None) -> IBMTargetProcessClient:
    """
    Get the IBM Targetprocess client with credentials.

    Args:
        version: Optional API version. Defaults to 'v1' if not provided.

    Returns:
        A new instance of the IBM Targetprocess client.
    """
    credentials = get_tool_credentials(Systems.IBM_TARGETPROCESS)

    selected_version = version if version else "v1"

    ibmtargetprocess_client = IBMTargetProcessClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        access_token=credentials[CredentialKeys.BEARER_TOKEN],
        version=selected_version,
    )
    return ibmtargetprocess_client
