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


class ZendeskClient:
    """A remote client for Zendesk."""

    def __init__(self, base_url: str, bearer_token: str, version: str = "v2"):
        """
        Initialize the Zendesk client.

        Args:
            base_url: The base URL for the Zendesk API.
            bearer_token: The bearer token or API token.
            version: The version of Zendesk API. Defaults to "v2".
        """
        self.base_url = base_url
        self.version = version
        self.headers = {
            "Authorization": f"Bearer {bearer_token}",
        }

    def _request(
        self,
        method: str,
        entity: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        get_content: Optional[bool] = False,
    ) -> Union[Dict[str, Any], ErrorDetails, int]:
        """
        Perform an HTTP request to the Zendesk API.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE).
            entity: API entity path (e.g., "tickets", "users").
            params: Query parameters for GET requests. Defaults to None.
            payload: JSON body (dict) or raw bytes for uploads. Defaults to None.
            get_content: If True and method is GET, return raw content instead of JSON.

        Returns:
            Dict[str, Any]: JSON response or structured error details.
            int: HTTP status code for DELETE requests without response content.
            ErrorDetails: Error information if the request fails.
        """
        url = f"{self.base_url}/api/{self.version}/{entity}"
        response: Optional[requests.Response] = None

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
                return {"status_code": response.status_code}

            # GET with binary content
            if method == HTTPMethod.GET and get_content:
                return {
                    "status_code": response.status_code,
                    "content": response.content,
                }

            # Parse JSON and handle empty responses
            try:
                response_json = response.json()
                if method == HTTPMethod.GET and not response_json:
                    return no_data_in_get_request(response=response)

                response_json["status_code"] = response.status_code
                return response_json
            except ValueError:
                return {
                    "status_code": response.status_code,
                    "content": response.content,
                }

        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def get_request(
        self,
        entity: str,
        params: Optional[Dict[str, Any]] = None,
        content: Optional[bool] = False,
    ) -> Union[Dict[str, Any], ErrorDetails]:
        """
        Executes a GET request against Zendesk API.

        Args:
            entity: API entity path (e.g., "tickets", "users").
            params: Query parameters for the REST API.
            content: If True, return raw content instead of parsed JSON.

        Returns:
            The JSON response from the Zendesk REST API.
        """
        result = self._request(HTTPMethod.GET, entity, params=params, get_content=content)
        if isinstance(result, int):
            raise TypeError("Unexpected int return for GET request")
        return result

    def post_request(
        self,
        entity: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Union[Dict[str, Any], ErrorDetails]:
        """
        Executes a POST request against Zendesk API.

        Args:
            entity: API entity path (e.g., "tickets", "users").
            payload: The request payload.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the Zendesk REST API.
        """
        result = self._request(HTTPMethod.POST, entity, params=params, payload=payload)
        if isinstance(result, int):
            raise TypeError("Unexpected int return for POST request")
        return result

    def put_request(
        self,
        entity: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Union[Dict[str, Any], ErrorDetails]:
        """
        Executes a PUT request against Zendesk API.

        Args:
            entity: The specific entity to make the request against.
            payload: The request payload.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the Zendesk REST API or the API request error details if an error occurs during the API call.
        """
        result = self._request("PUT", entity, params=params, payload=payload)
        if isinstance(result, int):
            raise TypeError("Unexpected int return for PUT request")
        return result

    def patch_request(
        self,
        entity: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Union[Dict[str, Any], ErrorDetails]:
        """
        Executes a PATCH request against Zendesk API.

        Args:
            entity: API entity path (e.g., "tickets", "users").
            payload: The request payload.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the Zendesk REST API.
        """
        result = self._request(HTTPMethod.PATCH, entity, params=params, payload=payload)
        if isinstance(result, int):
            raise TypeError("Unexpected int return for PATCH request")
        return result

    def delete_request(
        self,
        entity: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Union[int, Dict[str, Any], ErrorDetails]:
        """
        Executes a DELETE request against Zendesk API.

        Args:
            entity: API entity path (e.g., "tickets", "users").
            payload: The request payload.
            params: Query parameters for the REST API.

        Returns:
            The JSON response or status from the Zendesk REST API.
        """
        return self._request(HTTPMethod.DELETE, entity, params=params, payload=payload)


def get_zendesk_client() -> Union[ZendeskClient, ErrorDetails]:
    """
    Get the Zendesk client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of ZendeskClient.
    """
    try:
        credentials = get_tool_credentials(Systems.ZENDESK)
        return ZendeskClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
            version="v2",
        )
    except Exception as e:  # pylint: disable=broad-except
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Zendesk client initialization: {str(e)}",
            details=f"Caught error during Zendesk client initialization: {str(e)}",
            recommendation=None,
        )
