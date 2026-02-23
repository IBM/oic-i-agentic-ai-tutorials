from http import HTTPMethod, HTTPStatus
from typing import Any, Dict, Optional

import requests

from agent_ready_tools.clients.auth_manager import AdobeWorkfrontAuthManager
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class AdobeWorkfrontClient:
    """A remote client for Adobe Workfront."""

    def __init__(
        self,
        base_url: str,
        token_url: str,
        client_id: str,
        client_secret: str,
        initial_bearer_token: str,
        initial_refresh_token: str,
    ):
        """
        Args:
            base_url: The base URL for the Adobe Workfront API.
            token_url: The URL for authentication tokens for the Adobe Workfront API.
            client_id: The client ID authenticate with.
            client_secret: The client secret to authenticate with.
            initial_bearer_token: The initial bearer token from wxo-domains credentials file.
            initial_refresh_token: The initial refresh token from wxo-domains credentials file.
        """
        self.base_url = base_url
        self.auth_manager = AdobeWorkfrontAuthManager(
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            initial_bearer_token=initial_bearer_token,
            initial_refresh_token=initial_refresh_token,
        )
        self.headers = {"Content-Type": "application/json", "sessionID": initial_bearer_token}

    def _request_with_reauth(
        self,
        method: str,
        url: str,
        retries: int = 2,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """Makes a <method> request to the given URL with the given params and payload, retrying on
        token expiry."""
        for _ in range(retries):  # 1 retry

            self.headers["sessionID"] = self.auth_manager.get_bearer_token()
            response = requests.request(
                method=method,
                url=url,
                params=params,
                headers=self.headers,
                json=payload,
            )

            if response.status_code == HTTPStatus.UNAUTHORIZED:
                self.auth_manager.refresh_bearer_token()
            else:
                break

        return response

    def delete_request(
        self,
        entity: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
        version: str = "v20.0",
    ) -> int:
        """
        Executes a DELETE request against Adobe Workfront.

        Args:
            entity: The specific entity to make the request against.
            params: Query parameters for the REST API.
            payload: The request payload.
            version: The specific version of the API.

        Returns:
            The JSON response from the Adobe Workfront REST API.
        """

        response = self._request_with_reauth(
            HTTPMethod.DELETE,
            url=f"{self.base_url}/attask/api/{version}/{entity}",
            payload=payload,
            params=params,
        )
        response.raise_for_status()
        return response.status_code

    def patch_request(
        self,
        entity: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
        version: str = "v20.0",
    ) -> Dict[str, Any]:
        """
        Executes a PATCH request against Adobe Workfgront API.

        Args:
            entity: The specific entity to make the request against.
            params: Query parameters for the REST API.
            payload: The request payload.
            version: The specific version of the API.

        Returns:
            The JSON response from the Adobe Workfront REST API.
        """
        response = self._request_with_reauth(
            HTTPMethod.PATCH,
            url=f"{self.base_url}/attask/api/{version}/{entity}",
            payload=payload,
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def put_request(
        self,
        entity: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
        version: str = "v20.0",
    ) -> Dict[str, Any]:
        """
        Executes a PUT request against Adobe Workfront API.

        Args:
            entity: The specific entity to make the request against.
            params: Query parameters for the REST API.
            payload: The request payload.
            version: The specific version of the API.

        Returns:
            The JSON response from the Adobe Workfront REST API.
        """

        response = self._request_with_reauth(
            HTTPMethod.PUT,
            url=f"{self.base_url}/attask/api/{version}/{entity}",
            payload=payload,
            params=params,
        )

        response.raise_for_status()
        return response.json()

    def post_request(
        self,
        entity: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
        version: str = "v20.0",
    ) -> Dict[str, Any]:
        """
        Executes a POST request against Adobe Workfront API.

        Args:
            entity: The specific entity to make the request against.
            params: Query parameters for the REST API.
            payload: The request payload.
            version: The specific version of the API.

        Returns:
            The JSON response from the Adobe Workfront REST API.
        """

        response = self._request_with_reauth(
            HTTPMethod.POST,
            url=f"{self.base_url}/attask/api/{version}/{entity}",
            payload=payload,
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def get_request(
        self,
        entity: str,
        params: Optional[dict[str, Any]] = None,
        content: Optional[bool] = False,
        version: str = "v20.0",
    ) -> Dict[str, Any]:
        """
        Executes a GET request against Adobe Workfront API.

        Args:
            entity: The specific entity to make the request against.
            params: Query parameters for the REST API.
            content: This is optional parameter to retrieve the file content as text. Defaults to
                False.
            version: The specific version of the API.

        Returns:
            The JSON response from the Adobe Workfront REST API.
        """

        response = self._request_with_reauth(
            HTTPMethod.GET, url=f"{self.base_url}/attask/api/{version}/{entity}", params=params
        )

        response.raise_for_status()
        if content:
            return {"text": response.text, "headers": response.headers}
        return response.json()


def get_adobe_workfront_client() -> AdobeWorkfrontClient:
    """
    Get the adobe work front client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the adobe workfront client.
    """
    credentials = get_tool_credentials(Systems.ADOBEWORKFRONT)
    adobe_workfront_client = AdobeWorkfrontClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        token_url=credentials[CredentialKeys.TOKEN_URL],
        client_id=credentials[CredentialKeys.CLIENT_ID],
        client_secret=credentials[CredentialKeys.CLIENT_SECRET],
        initial_bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
        initial_refresh_token=credentials[CredentialKeys.REFRESH_TOKEN],
    )
    return adobe_workfront_client
