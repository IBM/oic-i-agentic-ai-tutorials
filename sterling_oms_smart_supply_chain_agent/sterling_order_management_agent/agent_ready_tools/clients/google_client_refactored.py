import json
from typing import Any, Dict, Optional, Union

import requests

from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    handling_exceptions,
)
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
    ) -> int | ErrorDetails:
        """
        Executes a DELETE request against Google API.

        Args:
            entity: The specific entity to make the request against.
            service: The Google API service to use (e.g., "drive", "storage"). Defaults to "drive".
            params: Query parameters for the REST API.
            payload: The request payload.
            version: The specific version of the API.

        Returns:
            The JSON response from the Google REST API or the API request error details if an error occurs during the API call.
        """
        url = f"{self.base_url}/{service}/{version}/{entity}"
        response: requests.Response | None = None
        try:
            response = requests.delete(
                url=url,
                json=payload,
                params=params,
                headers=self.headers,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        return response.status_code

    def patch_request(
        self,
        entity: str,
        service: str = "drive",
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
        version: str = "v3",
    ) -> Dict[str, Any] | ErrorDetails:
        """
        Executes a PATCH request against Google API.

        Args:
            entity: The specific entity to make the request against.
            service: The Google API service to use (e.g., "drive", "storage"). Defaults to "drive".
            params: Query parameters for the REST API.
            payload: The request payload.
            version: The specific version of the API.

        Returns:
            The JSON response from the Google REST API or the API request error details if an error occurs during the API call.
        """
        url = f"{self.base_url}/{service}/{version}/{entity}"
        response: requests.Response | None = None
        try:
            response = requests.patch(
                url=f"{self.base_url}/{service}/{version}/{entity}",
                json=payload,
                params=params,
                headers=self.headers,
            )
            response.raise_for_status()
            json_response = response.json()
            return json_response
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def put_request(
        self,
        entity: str,
        service: str = "drive",
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
        version: str = "v3",
    ) -> Dict[str, Any] | ErrorDetails:
        """
        Executes a PUT request against Google API.

        Args:
            entity: The specific entity to make the request against.
            service: The Google API service to use (e.g., "drive", "storage"). Defaults to "drive".
            params: Query parameters for the REST API.
            payload: The request payload.
            version: The specific version of the API.

        Returns:
            The JSON response from the Google REST API or the API request error details if an error occurs during the API call.
        """
        url = f"{self.base_url}/{service}/{version}/{entity}"
        response: requests.Response | None = None
        try:
            response = requests.put(
                url=url,
                json=payload,
                params=params,
                headers=self.headers,
            )

            response.raise_for_status()
            json_response = response.json()
            return json_response
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def post_request(
        self,
        entity: str,
        service: str = "drive",
        params: Optional[dict[str, Any]] = None,
        payload: Optional[Union[dict[str, Any], bytes, bytearray]] = None,
        version: str = "v3",
    ) -> Dict[str, Any] | ErrorDetails:
        """
        Executes a POST request against Google API.

        Args:
            entity: The specific entity to make the request against.
            service: The Google API service to use (e.g., "drive", "storage"). Defaults to "drive".
            params: Query parameters for the REST API.
            payload: The request payload.
            version: The specific version of the API.

        Returns:
            The JSON response from the Google REST API or the API request error details if an error occurs during the API call.
        """
        data, json_payload = (
            (payload, None) if isinstance(payload, (bytes, bytearray)) else (None, payload)
        )
        url = f"{self.base_url}/{service}/{version}/{entity}"
        response: requests.Response | None = None
        try:
            response = requests.post(
                url=url,
                json=json_payload,
                data=data,
                params=params,
                headers=self.headers,
            )
            response.raise_for_status()
            json_response = response.json()
            return json_response
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def get_request(
        self,
        entity: str,
        service: str = "drive",
        params: Optional[dict[str, Any]] = None,
        content: Optional[bool] = False,
        version: str = "v3",
    ) -> Dict[str, Any] | ErrorDetails:
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
            The JSON response from the Google REST API or the API request error details if an error occurs during the API call.
        """
        url = f"{self.base_url}/{service}/{version}/{entity}"
        response: requests.Response | None = None
        try:
            response = requests.get(url=url, params=params, headers=self.headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)
        if content:
            return {"text": response.text, "headers": response.headers}
        return response.json()


def get_google_client() -> GoogleClient | ErrorDetails:
    """
    Get the google client with credentials or the error details if an error occurs during creating
    new instance of the Google client.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the google client or the error details if an error occurs during creating new instance of the Google client.
    """
    try:
        credentials = get_tool_credentials(Systems.GOOGLE)
        google_client = GoogleClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
        )
    except (AssertionError, ValueError, requests.exceptions.RequestException) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Google client initialization:{str(e)}",
            details=f"Caught error during Google client initialization:{str(e)}",
            recommendation=None,
        )
    return google_client
