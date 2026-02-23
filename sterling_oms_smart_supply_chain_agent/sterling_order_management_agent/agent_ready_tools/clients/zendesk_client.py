from http import HTTPMethod
from typing import Any, Dict, Optional, Union

import requests

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
        payload: Optional[Union[Dict[str, Any], bytes]] = None,
        get_content: Optional[bool] = False,
    ) -> Dict[str, Any]:
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
        """
        url = f"{self.base_url}/api/{self.version}/{entity}"
        response: Optional[requests.Response] = None

        response = requests.request(
            method=method,
            url=url,
            headers=self.headers,
            params=params,
            json=payload if isinstance(payload, dict) else None,
            data=payload if isinstance(payload, bytes) else None,
        )
        response.raise_for_status()
        result: Dict[str, Any] = {}
        if response.content and not get_content:
            try:
                result = response.json()
            except ValueError:
                result = {"content": response.content}
        elif get_content:
            result = {"content": response.content}

        result["status_code"] = response.status_code
        return result

    def get_request(
        self,
        entity: str,
        params: Optional[Dict[str, Any]] = None,
        content: Optional[bool] = False,
    ) -> Dict[str, Any]:
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
        return result

    def post_request(
        self,
        entity: str,
        payload: Optional[Union[Dict[str, Any], bytes]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a POST request against Zendesk API.

        Args:
            entity: API entity path (e.g., "tickets", "users").
            payload: The request payload (dict for JSON, bytes for uploads).
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the Zendesk REST API.
        """
        result = self._request(HTTPMethod.POST, entity, params=params, payload=payload)
        return result

    def put_request(
        self,
        entity: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a PUT request against Zendesk API.

        Args:
            entity: The specific entity to make the request against.
            payload: The request payload.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the Zendesk REST API.
        """
        result = self._request("PUT", entity, params=params, payload=payload)
        return result

    def patch_request(
        self,
        entity: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
        return result

    def delete_request(
        self,
        entity: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a DELETE request against Zendesk API.

        Args:
            entity: API entity path (e.g., "tickets", "users").
            payload: The request payload.
            params: Query parameters for the REST API.

        Returns:
            The JSON response or status from the Zendesk REST API.
        """
        result = self._request(HTTPMethod.DELETE, entity, params=params, payload=payload)
        return result


def get_zendesk_client() -> ZendeskClient:
    """
    Get the Zendesk client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of ZendeskClient.
    """
    credentials = get_tool_credentials(Systems.ZENDESK)
    return ZendeskClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
        version="v2",
    )
