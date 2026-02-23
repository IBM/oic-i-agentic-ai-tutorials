from typing import Any, Dict, List, Optional

import requests

from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    handling_exceptions,
    no_data_in_get_request,
)
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class SeismicTokenException(Exception):
    """Class for reporting errors that occur when trying to obtain seismic token."""

    message: str = "Failed to fetch Bearer token for Seismic client"

    def __str__(self) -> str:
        return self.message


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
            bearer_token: The bearer token to authenticate with fetched from Wxo connection-manager
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
        search_key: Optional[str] = None,
    ) -> Any | ErrorDetails:
        """
        Private method which executes a GET request against a Seismic API.

        Args:
            endpoint: The specific endpoint to make the request against.
            category: The specific category of the API, usually but not limited to "reporting" or
                "integration"
            version: The specific version of the API, usually but not limited to "v2"
            params: Query parameters for the REST API.
            custom_path_suffix: URL Path components for the REST API.
            search_key: The field in the API response that should be checked for the presence of data.

        Returns:
            The JSON response from the Seismic REST API of Any type
            or the API request error details if an error occurs during the API call.
        """
        url = f"{self.base_url}/{category}/{version}/{endpoint}"
        if custom_path_suffix:
            url += f"/{custom_path_suffix}"
        response: requests.Response | None = None
        try:
            response = requests.get(
                url=url,
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            response_json = response.json()
            if search_key and not response_json.get(search_key, None):
                return no_data_in_get_request(response=response)

        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        return response_json

    def get_request(
        self,
        endpoint: str,
        category: str,
        version: str = "v2",
        params: Optional[Dict[str, Any]] = None,
        custom_path_suffix: Optional[str] = None,
        search_key: Optional[str] = None,
    ) -> Dict[str, Any] | ErrorDetails:
        """
        Executes a GET request against a Seismic API.

        Args:
            endpoint: The specific endpoint to make the request against.
            category: The specific category of the API, usually but not limited to "reporting" or
                "integration"
            version: The specific version of the API, usually but not limited to "v2"
            params: Query parameters for the REST API.
            custom_path_suffix: URL Path components for the REST API.
            search_key: The field in the API response that should be checked for the presence of data.

        Returns:
            The JSON response from the Seismic REST API or the API request error details if an error occurs during the API call.
        """
        return self._get_request(
            endpoint=endpoint,
            category=category,
            version=version,
            params=params,
            custom_path_suffix=custom_path_suffix,
            search_key=search_key,
        )

    def get_request_list(
        self,
        endpoint: str,
        category: str,
        version: str = "v2",
        params: Optional[Dict[str, Any]] = None,
        custom_path_suffix: Optional[str] = None,
    ) -> List[Dict[str, Any]] | ErrorDetails:
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
            The JSON response from the Seismic REST API for the case that the output is a list
            or the API request error details if an error occurs during the API call.
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
    ) -> Dict[str, Any] | ErrorDetails:
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
            The JSON response from the Seismic API or the API request error details if an error occurs during the API call.
        """
        url = f"{self.base_url}/{category}/{version}/{endpoint}"
        if custom_path_suffix:
            url += f"/{custom_path_suffix}"

        json_param = {"$format": "JSON"}
        response: requests.Response | None = None
        try:
            response = requests.post(
                url=url,
                headers=self.headers,
                json=payload,
                params=params | json_param if params else json_param,
            )
            response.raise_for_status()
            response_json = response.json()
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        return response_json


def get_seismic_client() -> SeismicClient | ErrorDetails:
    """
    Get the seismic client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the Seismic client or the error details object if an error occurs while initalizing the client and its credentials.
    """
    try:
        credentials = get_tool_credentials(Systems.SEISMIC)
        seismic_client = SeismicClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
        )
    except (
        AssertionError,
        ValueError,
        requests.exceptions.RequestException,
        SeismicTokenException,
    ) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Seismic client initialization:{str(e)}",
            details=f"Caught error during Seismic client initialization:{str(e)}",
            recommendation=None,
        )
    return seismic_client
