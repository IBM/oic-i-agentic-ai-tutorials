# Standard library imports
from typing import Any, Dict, Optional

# Third-party library imports
import requests

from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    handling_exceptions,
)
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class JiraClient:
    """A remote client for Jira."""

    def __init__(self, base_url: str, bearer_token: str, version: Optional[int] = 3):
        """
        Args:
            base_url: The base URL for the Jira API.
            bearer_token: The bearer token to authentication with, fetched from WxO connection-manager.
            version: The version of Jira API.
        """
        self.base_url = base_url
        self.version = version
        self.headers = {"Accept": "application/json", "Authorization": f"Bearer {bearer_token}"}
        self.cloud_id = self.__get_cloud_id()

    def __get_cloud_id(self) -> str:
        """Fetches the Atlassian 'cloud id' used to construct endpoints using the bearer token."""
        url = f"{self.base_url}/oauth/token/accessible-resources"

        response = requests.get(url=url, headers=self.headers)
        response.raise_for_status()
        resp = response.json()

        assert len(resp) > 0, f"Unexpected empty response for endpoint {url}"
        cloud_id = resp[0].get("id")
        assert cloud_id, f"Missing Atlassian Cloud ID value in response: {resp}"

        return str(cloud_id)

    def get_request(
        self,
        entity: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a GET request against the provided entity.

        Args:
            entity: The entity to query.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the Jira API or the API request error details if an error occurs during the API call.
        """
        url = f"{self.base_url}/ex/jira/{self.cloud_id}/rest/api/{self.version}/{entity}"
        response: requests.Response | None = None

        try:
            response = requests.get(url=url, headers=self.headers, params=params)
            response.raise_for_status()
            result = response.json()

        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        return result

    def post_request(
        self,
        entity: str,
        payload: dict[str, Any],
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a generic post request against the Jira API.

        Args:
            entity: The entity to query.
            payload: A dictionary containing the input payload.
            headers: A dictionary containing the request headers (Optional).

        Returns:
            The JSON response from the Jira API or the API request error details if an error occurs during the API call.
        """
        headers = headers | self.headers if headers else self.headers
        url = f"{self.base_url}/ex/jira/{self.cloud_id}/rest/api/{self.version}/{entity}"
        response: requests.Response | None = None

        try:
            response = requests.post(
                url=url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()
            result["status_code"] = response.status_code

        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        return result

    def update_request(self, entity: str, payload: dict[str, Any]) -> dict[str, Any] | ErrorDetails:
        """
        Executes the update request against the provided entity in Jira API.

        Args:
            entity: The entity to query.
            payload: A dictionary containing the input payload.

        Returns:
            The JSON response from the Jira API or the API request error details if an error occurs during the API call.
        """

        url = f"{self.base_url}/ex/jira/{self.cloud_id}/rest/api/{self.version}/{entity}"
        response: requests.Response | None = None

        try:
            response = requests.patch(url=url, json=payload, headers=self.headers)
            response.raise_for_status()
            result = response.json()
            result["status_code"] = response.status_code

        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        return result

    def delete_request(
        self, entity: str, payload: Optional[dict[str, Any]] = None
    ) -> int | ErrorDetails:
        """
        Executes a generic delete request against the Jira API.

        Args:
            entity: The entity to query.
            payload: A dictionary containing the input payload.

        Returns:
            The status code of the request or the API request error details if an error occurs during the API call.
        """
        url = f"{self.base_url}/ex/jira/{self.cloud_id}/rest/api/{self.version}/{entity}"
        response: requests.Response | None = None

        try:
            response = requests.delete(
                url=url,
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()

        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        return response.status_code

    def put_request(self, entity: str, payload: dict[str, Any]) -> dict[str, Any] | ErrorDetails:
        """
        Executes the put request against the provided entity in Jira API.

        Args:
            entity: The entity to query.
            payload: A dictionary containing the input payload.

        Returns:
            The JSON response from the Jira API or the API request error details if an error occurs during the API call.
        """

        url = f"{self.base_url}/ex/jira/{self.cloud_id}/rest/api/{self.version}/{entity}"
        response: requests.Response | None = None

        try:
            response = requests.put(url=url, json=payload, headers=self.headers)
            response.raise_for_status()
            result = {}
            if response.content:
                result = response.json()
            else:
                result["status_code"] = response.status_code

        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        return result


def get_jira_client() -> JiraClient | ErrorDetails:
    """
    Get the jira client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!
    To test, either mock this call or call the client directly.

    Returns:
        A new instance of JiraClient or the error details object if an error occurs while initializing the client and its credentials.
    """
    try:
        credentials = get_tool_credentials(system=Systems.JIRA)
        jira_client = JiraClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
        )

    except (AssertionError, ValueError, KeyError, requests.exceptions.RequestException) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Jira client initialization:{str(e)}",
            details=f"Caught error during Jira client initialization:{str(e)}",
            recommendation=None,
        )

    return jira_client
