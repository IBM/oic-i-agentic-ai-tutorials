from typing import Any, Dict, Optional

import requests

from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class MicrosoftClient:
    """A remote client for Microsoft Graph API."""

    VERSION_1 = "v1.0"

    def __init__(
        self,
        token: str,
        base_url: str,
    ):
        """
        Args:
            token: The access token to authenticate with.
            base_url: The Microsoft Graph API URL.
        """

        self.base_url = base_url
        self.__user_resource_path = "me"
        self.token = token

    def get_request(
        self,
        endpoint: str,
        version: str = VERSION_1,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Executes a GET request against a Microsoft Graph API.

        Args:
            endpoint: The specific endpoint to make the request against.
            version: The specific version of the API, usually but not limited to "v1.0"
            params: Query parameters for the request.

        Returns:
            The JSON response from the request.
        """
        headers = {"Authorization": f"Bearer {self.token}"}

        response = requests.get(
            url=f"{self.base_url}/{version}/{endpoint}",
            headers=headers,
            params=params,
        )

        response.raise_for_status()
        result = response.json()
        result["status_code"] = response.status_code
        return result

    def post_request(
        self,
        endpoint: str,
        data: dict,
        version: str = VERSION_1,
        headers: Optional[Dict[str, str]] = None,
    ) -> dict[str, Any]:
        """
        Executes a POST request against a Microsoft Graph API.

        Args:
            endpoint: The specific endpoint to make the request against.
            data: The Input data request.
            version: The specific version of the API, usually but not limited to "v1.0"
            headers: The headers value for the request.

        Returns:
            The JSON response from the request.
        """
        if headers is None:
            headers = {"Authorization": f"Bearer {self.token}"}
        else:
            headers["Authorization"] = f"Bearer {self.token}"

        response = requests.post(
            url=f"{self.base_url}/{version}/{endpoint}",
            headers=headers,
            json=data,
        )
        response.raise_for_status()
        result = {}
        if response.content:
            result = response.json()

        result["status_code"] = response.status_code
        return result

    def update_request(self, endpoint: str, data: dict, version: str = VERSION_1) -> dict[str, Any]:
        """
        Executes an update (PATCH) request against the Microsoft Graph API.

        Args:
            endpoint: The specific endpoint to make the request against. The endpoint should contain
                the entity ID to be updated.
            data: A dictionary containing the input payload.
            version: The specific version of the API, usually but not limited to "v1.0"

        Returns:
            The JSON response from the request.
        """
        headers = {"Authorization": f"Bearer {self.token}"}

        response = requests.patch(
            url=f"{self.base_url}/{version}/{endpoint}",
            headers=headers,
            json=data,
        )

        response.raise_for_status()
        result = {}
        if response.content:
            result = response.json()
        else:
            result["status_code"] = response.status_code
        return result

    def delete_request(self, endpoint: str, version: str = VERSION_1) -> int:
        """
        Executes a DELETE request against the Microsoft Graph API.

        Args:
            endpoint: The specific endpoint to make the request against. The endpoint should contain
                the entity ID to be deleted.
            version: The specific version of the API, usually but not limited to "v1.0"

        Returns:
            The status code of the request.
        """
        headers = {"Authorization": f"Bearer {self.token}"}

        response = requests.delete(url=f"{self.base_url}/{version}/{endpoint}", headers=headers)

        response.raise_for_status()
        return response.status_code

    def put_request(
        self,
        endpoint: str,
        data: Any = None,
        version: str = VERSION_1,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Executes a PUT request against a Microsoft Graph API.

        Args:
            endpoint: Graph endpoint (e.g. "sites/{site_id}/drive/root:/file.txt:/content")
            data: Request body or binary data to send.
            version: API version, default "v1.0".
            headers: Optional headers dict.
            params: Optional query parameters.

        Returns:
            Parsed JSON response plus a "status_code" key.
        """
        if headers is None:
            headers = {"Authorization": f"Bearer {self.token}"}
        else:
            headers["Authorization"] = f"Bearer {self.token}"

        response = requests.put(
            url=f"{self.base_url}/{version}/{endpoint}",
            headers=headers,
            params=params,
            data=data,
        )
        response.raise_for_status()

        result = {}
        if response.content:
            result = response.json()
        result["status_code"] = response.status_code
        return result

    def get_user_resource_path(self) -> str:
        """
        Returns the first part of the resource path associated with the MicrosoftClient instance.

        Returns:
            The first part of the resource path.
        """
        return self.__user_resource_path


def get_microsoft_client() -> MicrosoftClient:
    """
    Get the microsoft client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the Microsoft client.
    """
    credentials = get_tool_credentials(Systems.MICROSOFT)
    microsoft_client = MicrosoftClient(
        token=credentials[CredentialKeys.BEARER_TOKEN],
        base_url=credentials[CredentialKeys.BASE_URL],
    )
    return microsoft_client
