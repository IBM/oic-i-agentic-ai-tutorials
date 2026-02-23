import json
from typing import Any, Dict, List, Optional, Union

import requests
from requests.exceptions import RequestException

from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class CoupaClient:
    """A remote client for Coupa."""

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
    ):
        """
        Args:
            base_url: The base URL for the Coupa API.
            bearer_token: The token for authentication tokens for the Coupa API (OAuth2).
        """
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    # TODO: modularize in followup PR so there's less repetition of the try except block
    def delete_request(
        self,
        resource_name: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Union[int, Dict[str, Any]]:
        """
        Executes a DELETE request against Coupa API.

        Args:
            resource_name: The specific resource to make the request against.
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            HTTP status code on success, or an error dictionary on failure.
        """

        response = None
        try:
            response = requests.delete(
                url=f"{self.base_url}/api/{resource_name}",
                headers=self.headers,
                json=payload,
                params=json.dumps(params),
            )
            response.raise_for_status()
            return response.status_code
        except RequestException:
            if response is not None:
                response_json = {
                    "errors": {
                        "error_message": "Delete request failed",
                        "status_code": getattr(response, "status_code", "Unknown"),
                    }
                }
            else:
                # connection error, timeout, etc.
                response_json = {
                    "errors": {
                        "error_message": "No response received (request failed before getting a response)",
                    }
                }

            return response_json

    def patch_request(
        self,
        resource_name: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a PATCH request against Coupa API.

        Args:
            resource_name: The specific resource to make the request against.
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            The JSON response from the Coupa REST API.
        """
        response = None
        try:
            response = requests.patch(
                url=f"{self.base_url}/api/{resource_name}",
                headers=self.headers,
                json=payload,
                params=json.dumps(params),
            )
            response.raise_for_status()
            return response.json()
        except RequestException:
            if response is not None:
                try:
                    response_json = response.json()
                except ValueError:
                    # handle the case where response content is not JSON (e.g. 404)
                    response_json = {
                        "errors": {
                            "error_message": "Non-JSON response",
                            "status_code": getattr(response, "status_code", "Unknown"),
                        }
                    }
            else:
                # connection error, timeout, etc.
                response_json = {
                    "errors": {
                        "error_message": "No response received (request failed before getting a response)",
                    }
                }

            return response_json

    def put_request(
        self,
        resource_name: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a PUT request against Coupa API.

        Args:
            resource_name: The specific resource to make the request against.
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            The JSON response from the Coupa REST API.
        """
        response = None
        try:
            response = requests.put(
                url=f"{self.base_url}/api/{resource_name}",
                headers=self.headers,
                json=payload,
                params=json.dumps(params),
            )
            response.raise_for_status()
            return response.json()
        except RequestException:
            if response is not None:
                try:
                    response_json = response.json()
                except ValueError:
                    # handle the case where response content is not JSON (e.g. 404)
                    response_json = {
                        "errors": {
                            "error_message": "Non-JSON response",
                            "status_code": getattr(response, "status_code", "Unknown"),
                        }
                    }
            else:
                # connection error, timeout, etc.
                response_json = {
                    "errors": {
                        "error_message": "No response received (request failed before getting a response)",
                    }
                }

            return response_json

    def post_request(
        self,
        resource_name: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a POST request against Coupa API.

        Args:
            resource_name: The specific resource to make the request against.
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            The JSON response from the Coupa REST API.
        """
        response = None
        try:
            response = requests.post(
                url=f"{self.base_url}/api/{resource_name}",
                headers=self.headers,
                json=payload,
                params=json.dumps(params),
            )
            response.raise_for_status()
            return response.json()
        except RequestException:
            if response is not None:
                try:
                    response_json = response.json()
                except ValueError:
                    # handle the case where response content is not JSON (e.g. 404)
                    response_json = {
                        "errors": {
                            "error_message": "Non-JSON response",
                            "status_code": getattr(response, "status_code", "Unknown"),
                        }
                    }
            else:
                # connection error, timeout, etc.
                response_json = {
                    "errors": {
                        "error_message": "No response received (request failed before getting a response)",
                    }
                }

            return response_json

    def post_request_list(
        self,
        resource_name: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes a POST request against Coupa API.

        Args:
            resource_name: The specific resource to make the request against.
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            The JSON response from the Coupa REST API.
        """
        response = None
        try:
            response = requests.post(
                url=f"{self.base_url}/api/{resource_name}",
                headers=self.headers,
                json=payload,
                params=json.dumps(params),
            )
            response.raise_for_status()
            return response.json()
        except RequestException:
            if response is not None:
                try:
                    response_json = response.json()
                except ValueError:
                    # handle the case where response content is not JSON (e.g. 404)
                    response_json = [{"errors": "Non-JSON response"}]
            else:
                # connection error, timeout, etc.
                response_json = [
                    {
                        "errors": {
                            "error_message": "No response received (request failed before getting a response)",
                        }
                    }
                ]

            if isinstance(response_json, list):
                return response_json
            else:
                return [response_json]

    def get_request(
        self,
        resource_name: str,
        params: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a GET request against Coupa API.

        Args:
            resource_name: The specific resource to make the request against.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the Coupa REST API.
        """
        response = None
        try:
            response = requests.get(
                url=f"{self.base_url}/api/{resource_name}",
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except RequestException:
            if response is not None:
                try:
                    response_json = response.json()
                except ValueError:
                    # handle the case where response content is not JSON (e.g. 404)
                    response_json = {
                        "errors": {
                            "error_message": "Non-JSON response",
                            "status_code": getattr(response, "status_code", "Unknown"),
                        }
                    }
            else:
                # connection error, timeout, etc.
                response_json = {
                    "errors": {
                        "error_message": "No response received (request failed before getting a response)",
                    }
                }

            return response_json

    def get_request_list(
        self,
        resource_name: str,
        params: Optional[dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes a GET request against Coupa API.

        Args:
            resource_name: The specific resource to make the request against.
            params: Query parameters for the REST API.

        Returns:
            The JSON list response from the Coupa REST API.
        """
        response = None
        try:
            response = requests.get(
                url=f"{self.base_url}/api/{resource_name}",
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except RequestException:
            if response is not None:
                try:
                    response_json = response.json()
                except ValueError:
                    # handle the case where response content is not JSON (e.g. 404)
                    response_json = [{"errors": "Non-JSON response"}]
            else:
                # connection error, timeout, etc.
                response_json = [
                    {
                        "errors": {
                            "error_message": "No response received (request failed before getting a response)",
                        }
                    }
                ]

            if isinstance(response_json, list):
                return response_json
            else:
                return [response_json]


def get_coupa_client() -> CoupaClient:
    """
    Get the coupa client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of CoupaClient.
    """
    credentials = get_tool_credentials(Systems.COUPA)
    coupa_client = CoupaClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
    )
    return coupa_client
