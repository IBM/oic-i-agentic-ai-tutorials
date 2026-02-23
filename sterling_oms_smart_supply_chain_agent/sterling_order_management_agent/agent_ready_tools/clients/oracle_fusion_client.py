from typing import Any, Dict, Optional, Union

import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException

from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class OracleFusionClient:
    """A remote client for Oracle Fusion."""

    def __init__(self, base_url: str, username: str, password: str, version: str = "11.13.18.05"):
        """
        Args:
            base_url: The base URL for the Oracle Fusion API.
            username: The username to use for authentication against the Oracle Fusion API.
            password: The password to use for authentication against the Oracle Fusion API.
            version: The version of Oracle Fusion API.
        """
        self.base_url = base_url
        self.auth = HTTPBasicAuth(username, password)
        self.version = version

    def delete_request(
        self,
        resource_name: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, Any]] = None,
    ) -> Union[int, Dict[str, Any]]:
        """
        Executes a DELETE request against Oracle Fusion API.

        Args:
            resource_name: The specific resource to make the request against.
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            HTTP status code on success, or an error dictionary on failure.
        """
        if headers is None:
            headers = {}
        if params is None:
            params = {}

        response = None
        try:
            response = requests.delete(
                url=f"{self.base_url}/fscmRestApi/resources/{self.version}/{resource_name}",
                headers=headers,
                params=params,
                auth=self.auth,
            )
            response.raise_for_status()
            return response.json()
        except RequestException:
            if response is not None:
                try:
                    response_json = {"errors": response.text}
                except ValueError:
                    # handle the case where response content is not JSON (e.g. 404)
                    response_json = {"errors": "Non-JSON response"}
            else:
                # connection error, timeout, etc.
                response_json = {
                    "errors": "No response received (request failed before getting a response)"
                }
            return response_json

    def patch_request(
        self,
        resource_name: str,
        payload: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a PATCH request against Oracle Fusion API.

        Args:
            resource_name: The specific resource to make the request against.
            payload: The request payload.
            params: Query parameters for the REST API.
            headers: Optional request headers.

        Returns:
            The JSON response from the Oracle Fusion REST API.
        """
        if headers is None:
            headers = {}
        if params is None:
            params = {}
        if payload is None:
            payload = {}
        response = None
        try:
            response = requests.patch(
                url=f"{self.base_url}/fscmRestApi/resources/{self.version}/{resource_name}",
                headers=headers,
                params=params,
                json=payload,
                auth=self.auth,
            )
            response.raise_for_status()
            return response.json()
        except RequestException:
            if response is not None:
                try:
                    response_json = {"errors": response.text}
                except ValueError:
                    # handle the case where response content is not JSON (e.g. 404)
                    response_json = {"errors": "Non-JSON response"}
            else:
                # connection error, timeout, etc.
                response_json = {
                    "errors": "No response received (request failed before getting a response)"
                }
            return response_json

    def post_request(
        self,
        resource_name: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a POST request against Oracle Fusion API.

        Args:
            resource_name: The specific resource to make the request against.
            params: Query parameters for the REST API.
            headers: The optional request headers.
            payload: The request payload.

        Returns:
            The JSON response from the Oracle Fusion REST API.
        """
        if headers is None:
            headers = {}
        if params is None:
            params = {}

        response = None
        try:
            response = requests.post(
                url=f"{self.base_url}/fscmRestApi/resources/{self.version}/{resource_name}",
                headers=headers,
                params=params,
                json=payload,
                auth=self.auth,
            )
            response.raise_for_status()
            return response.json()
        except RequestException:
            if response is not None:
                try:
                    response_json = {"errors": response.text}
                except ValueError:
                    # handle the case where response content is not JSON (e.g. 404)
                    response_json = {"errors": "Non-JSON response"}
            else:
                # connection error, timeout, etc.
                response_json = {
                    "errors": "No response received (request failed before getting a response)"
                }
            return response_json

    def get_request(
        self,
        resource_name: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a GET request against Oracle Fusion API.

        Args:
            resource_name: The specific resource to make the request against.
            params: Query parameters for the REST API.
            headers: The optional request headers.

        Returns:
            The JSON list response from the Oracle Fusion REST API.
        """
        if headers is None:
            headers = {}
        if params is None:
            params = {}

        response = None
        try:
            response = requests.get(
                url=f"{self.base_url}/fscmRestApi/resources/{self.version}/{resource_name}",
                headers=headers,
                params=params,
                auth=self.auth,
            )
            response.raise_for_status()
            return response.json()
        except RequestException:
            if response is not None:
                try:
                    response_json = {"errors": response.text}
                except ValueError:
                    # handle the case where response content is not JSON (e.g. 404)
                    response_json = {"errors": "Non-JSON response"}
            else:
                # connection error, timeout, etc.
                response_json = {
                    "errors": "No response received (request failed before getting a response)"
                }
            return response_json


def get_oracle_fusion_client() -> OracleFusionClient:
    """
    Get the oracle fusion client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the Oracle Fusion client.
    """
    credentials = get_tool_credentials(Systems.ORACLE_FUSION)
    oracle_fusion_client = OracleFusionClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        username=credentials[CredentialKeys.USERNAME],
        password=credentials[CredentialKeys.PASSWORD],
    )
    return oracle_fusion_client
