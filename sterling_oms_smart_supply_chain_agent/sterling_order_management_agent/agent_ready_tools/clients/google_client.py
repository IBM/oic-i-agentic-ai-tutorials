from typing import Any, Dict, Optional, Union

import requests

from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class GoogleClient:
    """A remote client for Google."""

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
    ):
        """
        Args:
            base_url: The base URL for the Google API.
            bearer_token: The bearer token used to authenticate fetched from WxO connection-manager.
        """
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}",
        }

    def delete_request(
        self,
        entity: str,
        service: str = "drive",
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
        version: str = "v3",
    ) -> int:
        """
        Executes a DELETE request against Google API.

        Args:
            entity: The specific entity to make the request against.
            service: The Google API service to use (e.g., "drive", "storage"). Defaults to "drive".
            params: Query parameters for the REST API.
            payload: The request payload.
            version: The specific version of the API.

        Returns:
            The JSON response from the Google REST API.
        """
        response = requests.delete(
            url=f"{self.base_url}/{service}/{version}/{entity}",
            json=payload,
            params=params,
            headers=self.headers,
        )
        response.raise_for_status()
        return response.status_code

    def patch_request(
        self,
        entity: str,
        service: str = "drive",
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
        version: str = "v3",
    ) -> Dict[str, Any]:
        """
        Executes a PATCH request against Google API.

        Args:
            entity: The specific entity to make the request against.
            service: The Google API service to use (e.g., "drive", "storage"). Defaults to "drive".
            params: Query parameters for the REST API.
            payload: The request payload.
            version: The specific version of the API.

        Returns:
            The JSON response from the Google REST API.
        """
        response = requests.patch(
            url=f"{self.base_url}/{service}/{version}/{entity}",
            json=payload,
            params=params,
            headers=self.headers,
        )
        response.raise_for_status()
        return response.json()

    def put_request(
        self,
        entity: str,
        service: str = "drive",
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
        version: str = "v3",
    ) -> Dict[str, Any]:
        """
        Executes a PUT request against Google API.

        Args:
            entity: The specific entity to make the request against.
            service: The Google API service to use (e.g., "drive", "storage"). Defaults to "drive".
            params: Query parameters for the REST API.
            payload: The request payload.
            version: The specific version of the API.

        Returns:
            The JSON response from the Google REST API.
        """
        response = requests.put(
            url=f"{self.base_url}/{service}/{version}/{entity}",
            json=payload,
            params=params,
            headers=self.headers,
        )

        response.raise_for_status()
        return response.json()

    def post_request(
        self,
        entity: str,
        service: str = "drive",
        params: Optional[dict[str, Any]] = None,
        payload: Optional[Union[dict[str, Any], bytes, bytearray]] = None,
        version: str = "v3",
    ) -> Dict[str, Any]:
        """
        Executes a POST request against Google API.

        Args:
            entity: The specific entity to make the request against.
            service: The Google API service to use (e.g., "drive", "storage"). Defaults to "drive".
            params: Query parameters for the REST API.
            payload: The request payload.
            version: The specific version of the API.

        Returns:
            The JSON response from the Google REST API.
        """
        data, json_payload = (
            (payload, None) if isinstance(payload, (bytes, bytearray)) else (None, payload)
        )
        response = requests.post(
            url=f"{self.base_url}/{service}/{version}/{entity}",
            json=json_payload,
            data=data,
            params=params,
            headers=self.headers,
        )
        response.raise_for_status()
        return response.json()

    def get_request(
        self,
        entity: str,
        service: str = "drive",
        params: Optional[dict[str, Any]] = None,
        content: Optional[bool] = False,
        version: str = "v3",
    ) -> Dict[str, Any]:
        """
        Executes a GET request against Google API.

        Args:
            entity: The specific entity to make the request against.
            service: The Google API service to use (e.g., "drive", "storage"). Defaults to "drive".
            params: Query parameters for the REST API.
            content: This is optional parameter to retrieve the file content as text. Defaults to
                False.
            version: The specific version of the API.

        Returns:
            The JSON response from the Google REST API.
        """

        response = requests.get(
            url=f"{self.base_url}/{service}/{version}/{entity}", params=params, headers=self.headers
        )
        response.raise_for_status()
        if content:
            return {"text": response.text, "headers": response.headers}
        return response.json()


def get_google_client() -> GoogleClient:
    """
    Get the google client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the google client.
    """
    credentials = get_tool_credentials(Systems.GOOGLE)
    google_client = GoogleClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
    )
    return google_client
