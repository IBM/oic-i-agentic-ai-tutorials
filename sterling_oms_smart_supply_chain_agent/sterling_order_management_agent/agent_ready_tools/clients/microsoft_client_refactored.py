import json
from typing import Any, Dict, Optional

import requests

from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    handling_exceptions,
    no_data_in_get_request,
)
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
        content: bool = False,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a GET request against a Microsoft Graph API or the API request error details if an
        error occurs during the API call.

        Args:
            endpoint: The specific endpoint to make the request against.
            version: The specific version of the API, usually but not limited to "v1.0"
            params: Query parameters for the request.
            content: If True, returns raw bytes instead of JSON. Default is False.

        Returns:
            JSON response by default, or raw binary content when content=True.
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.base_url}/{version}/{endpoint}"
        response: requests.Response | None = None
        try:
            response = requests.get(
                url=url,
                headers=headers,
                params=params,
            )

            response.raise_for_status()

            if content:
                return {"contentBytes": response.content}

            result = response.json()
            if len(result.get("values", [])) == 0:
                return no_data_in_get_request(response=response)
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)
        result["status_code"] = response.status_code
        return result

    def post_request(
        self,
        endpoint: str,
        data: dict,
        version: str = VERSION_1,
        headers: Optional[Dict[str, str]] = None,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a POST request against a Microsoft Graph API or the API request error details if an
        error occurs during the API call.

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
        url = f"{self.base_url}/{version}/{endpoint}"
        response: requests.Response | None = None
        try:
            response = requests.post(
                url=url,
                headers=headers,
                json=data,
            )
            response.raise_for_status()
            result = {}
            if response.content:
                result = response.json()
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        result["status_code"] = response.status_code
        return result

    def update_request(
        self, endpoint: str, data: dict, version: str = VERSION_1
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes an update (PATCH) request against the Microsoft Graph API or the API request error
        details if an error occurs during the API call.

        Args:
            endpoint: The specific endpoint to make the request against. The endpoint should contain
                the entity ID to be updated.
            data: A dictionary containing the input payload.
            version: The specific version of the API, usually but not limited to "v1.0"

        Returns:
            The JSON response from the request.
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.base_url}/{version}/{endpoint}"
        response: requests.Response | None = None
        try:
            response = requests.patch(
                url=url,
                headers=headers,
                json=data,
            )

            response.raise_for_status()
            result = {}
            if response.content:
                result = response.json()
            else:
                result["status_code"] = response.status_code
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)
        return result

    def delete_request(self, endpoint: str, version: str = VERSION_1) -> int | ErrorDetails:
        """
        Executes a DELETE request against the Microsoft Graph API or the API request error details
        if an error occurs during the API call.

        Args:
            endpoint: The specific endpoint to make the request against. The endpoint should contain
                the entity ID to be deleted.
            version: The specific version of the API, usually but not limited to "v1.0"

        Returns:
            The status code of the request.
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.base_url}/{version}/{endpoint}"
        response: requests.Response | None = None
        try:
            response = requests.delete(url=url, headers=headers)

            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)
        return response.status_code

    def put_request(
        self,
        endpoint: str,
        data: Any = None,
        version: str = VERSION_1,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a PUT request against a Microsoft Graph API or the API request error details if an
        error occurs during the API call.

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
        url = f"{self.base_url}/{version}/{endpoint}"
        response: requests.Response | None = None
        try:
            response = requests.put(
                url=url,
                headers=headers,
                params=params,
                data=data,
            )
            response.raise_for_status()
            result = {}
            if response.content:
                result = response.json()
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        result["status_code"] = response.status_code
        return result

    def get_user_resource_path(self) -> str:
        """
        Returns the first part of the resource path associated with the MicrosoftClient instance.

        Returns:
            The first part of the resource path.
        """
        return self.__user_resource_path


def get_microsoft_client() -> MicrosoftClient | ErrorDetails:
    """
    Get the microsoft client with credentials or the error details if an error occurs during
    creating new instance of the Microsoft client.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the Microsoft client.
    """
    try:
        credentials = get_tool_credentials(Systems.MICROSOFT)
        microsoft_client = MicrosoftClient(
            token=credentials[CredentialKeys.BEARER_TOKEN],
            base_url=credentials[CredentialKeys.BASE_URL],
        )
    except (AssertionError, ValueError, requests.exceptions.RequestException) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Microsoft client initialization:{str(e)}",
            details=f"Caught error during Microsoft client initialization:{str(e)}",
            recommendation=None,
        )
    return microsoft_client
