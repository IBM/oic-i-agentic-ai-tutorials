from http import HTTPMethod
from typing import Any, Dict, Optional, Union

import requests

from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    handling_exceptions,
    no_data_in_get_request,
)
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class AnsibleClient:
    """A client for interacting with Red Hat Ansible Automation Platform (AAP) using OAuth2."""

    def __init__(self, base_url: str, bearer_token: str, version: str = "v2"):
        """
        Initialize the Ansible client.

        Args:
            base_url: The base URL for the Red Hat Ansible API.
            bearer_token: The bearer token from wxo connections-manager.
            version: The version of Red Hat Ansible API. Defaults to "v2".
        """
        self.base_url = base_url
        self.version = version
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}",
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        get_content: Optional[bool] = False,
    ) -> Union[Dict[str, Any], ErrorDetails, int]:
        """
        Perform an HTTP request to the Ansible API.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE).
            endpoint: API endpoint path (e.g., "inventories", "job_templates/launch").
            params: Query parameters for GET requests. Defaults to None.
            payload: JSON body for POST, PATCH, or DELETE requests. Defaults to None.
            get_content: If True and method is GET, return raw content instead of JSON.

        Returns:
            Dict[str, Any]: JSON response from the API with added 'status' and 'http_code'.
            int: HTTP status code for DELETE requests without response content.
            ErrorDetails: Error information if the request fails.
        """
        url = f"{self.base_url}/api/{self.version}/{endpoint}"
        response: requests.Response | None = None

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=payload,
            )
            response.raise_for_status()

            # DELETE returns only status
            if method == HTTPMethod.DELETE:
                return {"http_code": response.status_code}

            # GET with binary content
            if method == HTTPMethod.GET and get_content:
                return {
                    "http_code": response.status_code,
                    "content": response.content,
                }

            # Parse JSON and handle empty responses
            try:
                response_json = response.json()
                if method == HTTPMethod.GET and not response_json:
                    return no_data_in_get_request(response=response)

                response_json["http_code"] = response.status_code
                return response_json
            except ValueError:
                return {
                    "http_code": response.status_code,
                    "content": response.content,
                }

        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def get_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        content: Optional[bool] = False,
    ) -> Union[Dict[str, Any], ErrorDetails]:
        """
        Perform a GET request to the Ansible API.

        Args:
            endpoint: API endpoint path (e.g., "inventories").
            params: Optional query parameters for the request.
            content: If True, return raw content instead of parsed JSON.

        Returns:
            Dict[str, Any]: JSON response from the API.
            ErrorDetails: Error information if the request fails.
        """
        result = self._request(HTTPMethod.GET, endpoint, params=params, get_content=content)
        if isinstance(result, int):
            raise TypeError("Unexpected int return for GET request")
        return result

    def post_request(
        self,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Union[Dict[str, Any], ErrorDetails]:
        """
        Perform a POST request to the Ansible API.

        Args:
            endpoint: API endpoint path (e.g., "job_templates/launch").
            payload: Optional JSON body for the request.
            params: Optional query parameters for the request.

        Returns:
            Dict[str, Any]: JSON response from the API.
            ErrorDetails: Error information if the request fails.
        """
        result = self._request(HTTPMethod.POST, endpoint, params=params, payload=payload)
        if isinstance(result, int):
            raise TypeError("Unexpected int return for POST request")
        return result

    def patch_request(
        self,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Union[Dict[str, Any], ErrorDetails]:
        """
        Perform a PATCH request to the Ansible API.

        Args:
            endpoint: API endpoint path (e.g., "inventories/5").
            payload: Optional JSON body for the request.
            params: Optional query parameters for the request.

        Returns:
            Dict[str, Any]: JSON response from the API.
            ErrorDetails: Error information if the request fails.
        """
        result = self._request(HTTPMethod.PATCH, endpoint, params=params, payload=payload)
        if isinstance(result, int):
            raise TypeError("Unexpected int return for PATCH request")
        return result

    def delete_request(
        self,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Union[int, Dict[str, Any], ErrorDetails]:
        """
        Perform a DELETE request to the Ansible API.

        Args:
            endpoint: API endpoint path (e.g., "inventories/5").
            payload: Optional JSON body for the request.
            params: Optional query parameters for the request.

        Returns:
            int: HTTP status code if no content is returned.
            Dict[str, Any]: JSON response if the API returns content.
            ErrorDetails: Error information if the request fails.
        """
        return self._request(HTTPMethod.DELETE, endpoint, params=params, payload=payload)


def get_ansible_client() -> Union[AnsibleClient, ErrorDetails]:
    """
    Initialize an AnsibleClient instance using stored credentials.

    NOTE: Do not call directly in unit tests.
    To test, either mock this call or instantiate AnsibleClient directly.

    Returns:
        AnsibleClient: A new instance of the Ansible client.
        ErrorDetails: If initialization fails.
    """
    try:
        credentials = get_tool_credentials(Systems.RED_HAT_ANSIBLE)
        return AnsibleClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
            version="v2",
        )
    except Exception as e:  # pylint: disable=broad-except
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Ansible client initialization: {str(e)}",
            details=f"Caught error during Ansible client initialization: {str(e)}",
            recommendation=None,
        )
