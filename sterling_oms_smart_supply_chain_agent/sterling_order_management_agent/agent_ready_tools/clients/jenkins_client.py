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


class JenkinsClient:
    """A remote client for interacting with the Jenkins API using Basic Auth."""

    def __init__(self, base_url: str, username: str, password: str):
        """
        Args:
            base_url: The base URL for Jenkins.
            username: Jenkins username.
            password: Jenkins API token.
        """
        self.base_url = base_url
        self.auth = (username, password)

    def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        get_content: Optional[bool] = False,
    ) -> Dict[str, Any] | ErrorDetails:
        """Makes a <method> request to the given Jenkins URL with optional params and payload."""
        response: requests.Response | None = None
        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                json=payload,
                auth=self.auth,
            )
            response.raise_for_status()

            if method == HTTPMethod.DELETE:
                return {"status": "success", "http_code": response.status_code}

            if method == HTTPMethod.GET and get_content:
                return {
                    "status": "success",
                    "http_code": response.status_code,
                    "content": response.content,
                }

            # Parse JSON and handle empty responses
            try:
                response_json = response.json()
                # Handle empty GET responses like GitLab
                if method == HTTPMethod.GET and not response_json:
                    return no_data_in_get_request(response=response)
                # Merge success metadata into top-level JSON
                response_json["status"] = "success"
                response_json["http_code"] = response.status_code
                return response_json
            except ValueError:
                # If response is not JSON, return raw content
                return {
                    "http_code": response.status_code,
                    "content": response.content,
                }

        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def get_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        content: Optional[bool] = False,
    ) -> Dict[str, Any] | ErrorDetails:
        """
        Sends a GET request to Jenkins.

        Args:
            endpoint: API endpoint path (e.g., "job").
            params: Optional query parameters.
            content: If True, return raw response text instead of JSON.

        Returns:
            A dictionary containing the JSON response and HTTP status code,
            or raw bytes if the response is not JSON.
        """
        return self._request(
            HTTPMethod.GET,
            url=f"{self.base_url}/{endpoint}",
            params=params,
            get_content=content,
        )

    def post_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any] | ErrorDetails:
        """
        Sends a POST request to Jenkins.

        Args:
            endpoint: API endpoint path (e.g., "job").
            params: Optional query parameters.
            payload: Optional request body as a dictionary.

        Returns:
            A dictionary containing the JSON response and HTTP status code.
        """
        return self._request(
            HTTPMethod.POST,
            url=f"{self.base_url}/{endpoint}",
            params=params,
            payload=payload,
        )

    def put_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any] | ErrorDetails:
        """
        Sends a PUT request to Jenkins.

        Args:
            endpoint: API endpoint path (e.g., "job/job_name").
            params: Optional query parameters.
            payload: Optional request body as a dictionary.

        Returns:
            A dictionary containing the JSON response and HTTP status code,
            or an ErrorDetails object if the request fails.
        """
        return self._request(
            HTTPMethod.PUT,
            url=f"{self.base_url}/{endpoint}",
            params=params,
            payload=payload,
        )

    def delete_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> int | ErrorDetails:
        """
        Sends a DELETE request to Jenkins.

        Args:
            endpoint: API endpoint path (e.g., "job/job_name").
            params: Optional query parameters.
            payload: Optional request body as a dictionary.

        Returns:
            The HTTP status code of the response, or an ErrorDetails object if the request fails.
        """
        response = self._request(
            HTTPMethod.DELETE,
            url=f"{self.base_url}/{endpoint}",
            params=params,
            payload=payload,
        )
        if isinstance(response, ErrorDetails):
            return response
        return response["http_code"]


def get_jenkins_client() -> JenkinsClient | ErrorDetails:
    """
    Create a JenkinsClient instance using stored credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!
    To test, either mock this call or instantiate JenkinsClient directly.

    Returns:
        An initialized JenkinsClient object.
    """
    try:
        credentials = get_tool_credentials(Systems.JENKINS)
        return JenkinsClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            username=credentials[CredentialKeys.USERNAME],
            password=credentials[CredentialKeys.PASSWORD],
        )
    except Exception as e:  # pylint: disable=broad-except
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Jenkins client initialization: {str(e)}",
            details=f"Caught error during Jenkins client initialization: {str(e)}",
            recommendation=None,
        )
