from http import HTTPMethod, HTTPStatus
from typing import Any, Dict, Optional

import requests

from agent_ready_tools.clients.auth_manager import WorkdayAuthManager
from agent_ready_tools.clients.clients_enums import AccessLevel
from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    handling_exceptions,
    no_data_in_get_request,
)
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems

RETRY_COUNT = 2


class WorkdayClient:
    """A remote client for Workday."""

    def __init__(
        self,
        base_url: str,
        token_url: str,
        tenant_name: str,
        client_id: str,
        client_secret: str,
        initial_bearer_token: str,
        initial_refresh_token: str,
        access_level: AccessLevel,
    ):
        """
        Args:
            base_url: The base URL for the Workday API.
            token_url: The URL for authentication tokens for the Workday API.
            tenant_name: The name of the tenant.
            client_id: The client ID authenticate with.
            client_secret: The client secret to authenticate with.
            initial_bearer_token: The initial bearer token from wxo-domains credentials file.
            initial_refresh_token: The initial refresh token from wxo-domains credentials file.
            access_level: The access level (account type) the auth tokens correspond to.
        """
        self.base_url = base_url
        self.tenant_name = tenant_name
        self.auth_manager = WorkdayAuthManager(
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            initial_bearer_token=initial_bearer_token,
            initial_refresh_token=initial_refresh_token,
            access_level=access_level,
        )
        self.headers = {
            "Content-Type": "application/json",
        }

    def _request_with_reauth(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> dict[str, Any] | ErrorDetails:
        """Makes a <method> request to the given URL with the given params and payload, retrying on
        token expiry."""
        for trial in range(RETRY_COUNT):  # 1 retry
            self.headers["Authorization"] = f"Bearer {self.auth_manager.get_bearer_token()}"
            response: requests.Response | None = None
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                json_response = response.json()

                if method == HTTPMethod.GET:
                    has_data = (
                        "data" in json_response and len(json_response.get("data", [])) > 0
                    ) or (
                        "Report_Entry" in json_response
                        and len(json_response.get("Report_Entry", [])) > 0
                    )

                    if not has_data:
                        return no_data_in_get_request(response=response)

                return json_response

            except Exception as e:  # pylint: disable=broad-except
                if (
                    response is not None
                    and response.status_code == HTTPStatus.UNAUTHORIZED
                    and trial < RETRY_COUNT - 1
                ):
                    self.auth_manager.refresh_bearer_token()
                else:
                    if response is not None:
                        return extract_error_details(response=response)
                    else:
                        return handling_exceptions(exception=e, url=url)
        assert response is not None  # mypy
        return extract_error_details(response=response)

    def get_request(
        self, url: str, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a GET request against Workday API.

        Args:
            url: The relative URL to make the request against.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the Workday API.
        """
        response = self._request_with_reauth(
            method=HTTPMethod.GET,
            url=f"{self.base_url}/{url}",
            params=params,
        )

        return response

    def get_href(self, href: str) -> dict[str, Any] | ErrorDetails:
        """
        Gets the contents from an href from Workday.

        Args:
            href: The href to be requested.

        Returns:
            The requested content.
        """
        response: requests.Response | None = None
        try:
            response = requests.get(
                url=href,
                headers=self.headers,
            )
            response.raise_for_status()
            json_response = response.json()
            # TODO- check if data is the correct key. The get_href method is not used by any tool at the moment
            if len(json_response.get("data", [])) == 0:
                return no_data_in_get_request(response=response)
            return json_response
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=href)

    def post_request(
        self, url: str, payload: Optional[dict[str, Any]] = None
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a POST request against Workday API.

        Args:
            url: The relative URL for the request.
            payload: The request payload.

        Returns:
            The JSON response from the Workday API.
        """
        response = self._request_with_reauth(
            method=HTTPMethod.POST,
            url=f"{self.base_url}/{url}",
            payload=payload,
        )
        return response

    def patch_request(
        self, url: str, payload: Optional[dict[str, Any]] = None
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a PATCH request against Workday API.

        Args:
            url: The relative URL for the request.
            payload: The request payload.

        Returns:
            The JSON response from the Workday API.
        """
        response = self._request_with_reauth(
            method=HTTPMethod.PATCH,
            url=f"{self.base_url}/{url}",
            payload=payload,
        )
        return response

    def put_request(
        self,
        url: str,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a PUT request against Workday API.

        Args:
            url: The relative URL to make the request against.
            json: The request payload.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the Workday API.
        """
        response = self._request_with_reauth(
            method=HTTPMethod.PUT,
            url=f"{self.base_url}/{url}",
            payload=json,
            params=params,
        )
        return response


# TODO We may want to consider removing `access_level` from here if we find a more elegant way to test tools that require multiple personas
def get_workday_client(
    access_level: AccessLevel = AccessLevel.EMPLOYEE,
) -> WorkdayClient | ErrorDetails:
    """
    Get the workday client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Args:
        access_level: It defines the persona of the logged-in user. By default, the value is
            EMPLOYEE.

    Returns:
        A new instance of the Workday client or the error details object if an error occurs while initializing the client and its credentials.
    """
    try:
        credentials = get_tool_credentials(system=Systems.WORKDAY, sub_category=access_level)
        workday_client = WorkdayClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            token_url=credentials[CredentialKeys.TOKEN_URL],
            tenant_name=credentials[CredentialKeys.TENANT_NAME],
            client_id=credentials[CredentialKeys.CLIENT_ID],
            client_secret=credentials[CredentialKeys.CLIENT_SECRET],
            initial_bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
            initial_refresh_token=credentials[CredentialKeys.REFRESH_TOKEN],
            access_level=access_level,
        )
    except (
        AssertionError,
        ValueError,
        KeyError,
        AttributeError,
        requests.exceptions.RequestException,
    ) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Workday client initialization:{str(e)}",
            details=f"Caught error during Workday client initialization:{str(e)}",
            recommendation=None,
        )
    return workday_client
