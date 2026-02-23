from http import HTTPMethod
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

T = Dict[str, Any] | ErrorDetails | int


class GitLabClient:
    """A remote client for interacting with the GitLab API using OAuth authentication."""

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
        version: str = "v4",
    ):
        """
        Args:
            base_url: The base URL for the Gitlab API.
            bearer_token: The bearer token from wxo connections-manager.
            version: The version of Gitlab API.
        """
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}",
        }
        self.version = version

    def get_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> T | bytes:
        """
        Sends a GET request to the GitLab API.

        Args:
            endpoint: API endpoint path (e.g., "projects").
            params: Optional query parameters.

        Returns:
            A dictionary containing the JSON response and HTTP status code,
            or raw bytes if the response is not JSON.
        """
        try:
            url = f"{self.base_url}/api/{self.version}/{endpoint}"

            response = requests.request(
                method=HTTPMethod.GET,
                url=url,
                headers=self.headers,
                params=params,
            )

            response.raise_for_status()

            try:
                result = response.json()
                if not result:
                    return no_data_in_get_request(response=response)
                return {
                    "status": "success",
                    "result": result,
                    "http_code": response.status_code,
                }
            except ValueError:
                # If response is not JSON, return raw content
                return response.content
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def post_request(self, endpoint: str, payload: Optional[Dict[str, Any]] = None) -> T:
        """
        Sends a POST request to the GitLab API.

        Args:
            endpoint: API endpoint path (e.g., "projects").
            payload: Optional request body as a dictionary.

        Returns:
            A dictionary containing the JSON response and HTTP status code.
        """
        try:
            url = f"{self.base_url}/api/{self.version}/{endpoint}"
            response = requests.request(
                method=HTTPMethod.POST,
                url=url,
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            result["http_code"] = response.status_code
            return result
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def put_request(self, endpoint: str, payload: Optional[Dict[str, Any]] = None) -> T:
        """
        Sends a PUT request to the GitLab API.

        Args:
            endpoint: API endpoint path (e.g., "projects/123").
            payload: Optional request body as a dictionary.

        Returns:
            A dictionary containing the JSON response and HTTP status code,
            or an ErrorDetails object if the request fails.
        """
        try:
            url = f"{self.base_url}/api/{self.version}/{endpoint}"
            response = requests.request(
                method=HTTPMethod.PUT,
                url=url,
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            result["http_code"] = response.status_code
            return result
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def delete_request(self, endpoint: str, payload: Optional[Dict[str, Any]] = None) -> T:
        """
        Sends a DELETE request to the GitLab API.

        Args:
            endpoint: API endpoint path (e.g., "projects/123").
            payload: Optional request body.

        Returns:
            The HTTP status code of the response.
        """
        try:
            url = f"{self.base_url}/api/{self.version}/{endpoint}"
            response = requests.request(
                method=HTTPMethod.DELETE,
                url=url,
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()

            return response.status_code
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)


def get_gitlab_client() -> GitLabClient:
    """
    create a GitLabClient instance using stored credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!
    To test, either mock this call or instantiate GitLabClient directly.

    Returns:
        An initialized GitLabClient object.
    """
    credentials = get_tool_credentials(Systems.GITLAB)
    return GitLabClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
        version="v4",
    )
