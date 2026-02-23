from typing import Any, Dict, List, Optional

import requests

from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class SeismicClient:
    """A remote client for Seismic."""

    INTEGRATION = "integration"
    REPORTING = "reporting"

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
    ):
        """
        Args:
            base_url: The base URL for the Seismic API.
            bearer_token: The bearer token to authenticate with fetched from WxO connection-manager.
        """
        self.base_url = base_url

        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {bearer_token}",
        }

    def _get_request(
        self,
        endpoint: str,
        category: str,
        version: str = "v2",
        params: Optional[Dict[str, Any]] = None,
        custom_path_suffix: Optional[str] = None,
    ) -> Any:
        """
        Private method which executes a GET request against a Seismic API.

        Args:
            endpoint: The specific endpoint to make the request against.
            category: The specific category of the API, usually but not limited to "reporting" or
                "integration"
            version: The specific version of the API, usually but not limited to "v2"
            params: Query parameters for the REST API.
            custom_path_suffix: URL Path components for the REST API.

        Returns:
            The JSON response from the Seismic REST API of Any type.
        """
        url = f"{self.base_url}/{category}/{version}/{endpoint}"
        if custom_path_suffix:
            url += f"/{custom_path_suffix}"

        response = requests.get(
            url=url,
            headers=self.headers,
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def get_request(
        self,
        endpoint: str,
        category: str,
        version: str = "v2",
        params: Optional[Dict[str, Any]] = None,
        custom_path_suffix: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes a GET request against a Seismic API.

        Args:
            endpoint: The specific endpoint to make the request against.
            category: The specific category of the API, usually but not limited to "reporting" or
                "integration"
            version: The specific version of the API, usually but not limited to "v2"
            params: Query parameters for the REST API.
            custom_path_suffix: URL Path components for the REST API.

        Returns:
            The JSON response from the Seismic REST API.
        """
        return self._get_request(
            endpoint=endpoint,
            category=category,
            version=version,
            params=params,
            custom_path_suffix=custom_path_suffix,
        )

    def get_request_list(
        self,
        endpoint: str,
        category: str,
        version: str = "v2",
        params: Optional[Dict[str, Any]] = None,
        custom_path_suffix: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes a GET request against a Seismic API.

        Args:
            endpoint: The specific endpoint to make the request against.
            category: The specific category of the API, usually but not limited to "reporting" or
                "integration"
            version: The specific version of the API, usually but not limited to "v2"
            params: Query parameters for the REST API.
            custom_path_suffix: URL Path components for the REST API.

        Returns:
            The JSON response from the Seismic REST API for the case that the output is a list.
        """
        return self._get_request(
            endpoint=endpoint,
            category=category,
            version=version,
            params=params,
            custom_path_suffix=custom_path_suffix,
        )

    # TODO: add function get_request_binary for when needed for operations like downloading binary file

    def post_request(
        self,
        endpoint: str,
        category: str,
        version: str = "v2",
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        custom_path_suffix: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes a POST request against a Seismic API.

        Args:
            endpoint: The specific endpoint to make the request against.
            category: The specific category of the API, usually but not limited to "reporting" or
                "integration"
            version: The specific version of the API, usually but not limited to "v2"
            payload: A dictionary containing the input payload (Optional).
            params: A dictionary containing the request params (Optional).
            custom_path_suffix: URL Path components for the REST API (Optional).

        Returns:
            The JSON response from the Seismic API.
        """
        url = f"{self.base_url}/{category}/{version}/{endpoint}"
        if custom_path_suffix:
            url += f"/{custom_path_suffix}"

        json_param = {"$format": "JSON"}
        response = requests.post(
            url=url,
            headers=self.headers,
            json=payload,
            params=params | json_param if params else json_param,
        )
        response.raise_for_status()
        return response.json()


def get_seismic_client() -> SeismicClient:
    """
    Get the seismic client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the Seismic client.
    """
    credentials = get_tool_credentials(Systems.SEISMIC)
    seismic_client = SeismicClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
    )
    return seismic_client
