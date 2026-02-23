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


class SalesloftClient:
    """A remote client for Salesloft."""

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
    ):
        """
        Args:
            base_url: The base URL for the Salesloft API.
            bearer_token: The bearer token to authenticate with fetched from Wxo connection-manager.
        """
        self.base_url = base_url
        self.bearer_token = bearer_token
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Bearer{bearer_token}",
        }

    def get_request(
        self,
        version: str,
        endpoint: str,
        path_parameter: Optional[str] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a GET request against Salesloft API.

        Args:
            version: The version of API.
            endpoint: The specific endpoint to make the request against, like "accounts".
            path_parameter: The path parameter for the REST API.
            data: The request payload data.

        Returns:
            The JSON response from the Salesloft API or the API request error details if an error occurs during the API call.
        """

        get_headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Accept": self.headers["Accept"],
        }
        if path_parameter:
            url = f"{self.base_url}/{version}/{endpoint}/{path_parameter}"
        else:
            url = f"{self.base_url}/{version}/{endpoint}"
        response: requests.Response | None = None
        try:
            response = requests.get(url, headers=get_headers, data=data)
            response.raise_for_status()
            response_json = response.json()
            if not response_json.get("data", None):
                return no_data_in_get_request(response=response)
            return response_json
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def post_request(
        self,
        version: str,
        endpoint: str,
        data: dict,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a POST request against a Salesloft API.

        Args:
            version: The version of API.
            endpoint: The specific endpoint to make the request against, like "accounts".
            data: The input data request.

        Returns:
            The JSON response from the Salesloft REST API or the API request error details if an error occurs during the API call.
        """
        post_headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Accept": self.headers["Accept"],
            "Content-Type": "multipart/form-data",
        }
        url = f"{self.base_url}/{version}/{endpoint}"
        response: requests.Response | None = None
        try:
            response = requests.post(url, headers=post_headers, data=data)
            response.raise_for_status()
            response_json = response.json()
            return response_json
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def put_request(
        self,
        version: str,
        endpoint: str,
        path_parameter: str,
        data: dict,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a PUT request against a Salesloft API.

        Args:
            version: The version of API.
            endpoint: The specific endpoint to make the request against, like "accounts".
            path_parameter: The path parameter for the REST API.
            data: The input data request.

        Returns:
            The JSON response from the Salesloft REST API or the API request error details if an error occurs during the API call.
        """
        put_headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Accept": self.headers["Accept"],
            "Content-Type": "multipart/form-data",
        }
        response: requests.Response | None = None
        try:
            url = f"{self.base_url}/{version}/{endpoint}/{path_parameter}"
            response = requests.put(url, headers=put_headers, data=data)
            response.raise_for_status()
            response_json = response.json()
            return response_json
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def delete_request(
        self,
        version: str,
        endpoint: str,
        path_parameter: str,
        data: Optional[dict[str, Any]] = None,
    ) -> int | ErrorDetails:
        """
        Executes a DELETE request against a Salesloft API.

        Args:
            version: The version of API.
            endpoint: The specific endpoint to make the request against, like "accounts".
            path_parameter: The path parameter for the REST API.
            data: The input data request.

        Returns:
            The status code responded from the Salesloft REST API or the API request error details if an error occurs during the API call.
        """
        delete_headers = {
            "Authorization": f"Bearer {self.bearer_token}",
        }
        url = f"{self.base_url}/{version}/{endpoint}/{path_parameter}"
        response: requests.Response | None = None
        try:
            response = requests.delete(url, headers=delete_headers, data=data)
            response.raise_for_status()
            return response.status_code
        except requests.exceptions.RequestException as e:
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)


def get_salesloft_client() -> SalesloftClient | ErrorDetails:
    """
    Get the Salesloft client with credentials.

    Returns:
        A new instance of the Salesloft client or the error details object if an error occurs while initializing the client and its credentials.
    """
    try:
        credentials = get_tool_credentials(Systems.SALESLOFT)
        salesloft_client = SalesloftClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
        )
    except (AssertionError, ValueError, requests.exceptions.RequestException) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Salesloft client initialization:{str(e)}",
            details=f"Caught error during Salesloft client initialization:{str(e)}",
            recommendation=None,
        )
    return salesloft_client
