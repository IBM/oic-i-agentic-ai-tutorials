from typing import Any, Optional

import requests

from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    handling_exceptions,
    no_data_in_get_request,
)
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class ServiceNowClient:
    """An HTTP Client for ServiceNow."""

    def __init__(self, base_url: str, bearer_token: str, path_url: str = "now/table"):
        """
        Args:
            base_url: The base URL for the Servicenow API.
            bearer_token: The bearer token to authenticate with.
            path_url: The table path url is default for the Servicenow API.
        """
        self.base_url = base_url
        self.bearer_token = bearer_token
        self.path_url = path_url

        self.headers = self._get_headers()

    def _get_headers(self) -> dict[str, Any]:
        """
        Generates Headers for REST API Calls for the client.

        Returns:
            A dictionary representing headers with auth credentials.
        """
        _headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }
        return _headers

    def get_request(
        self, entity: str, params: Optional[dict[str, Any]] = None, path_url: Optional[str] = None
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a GET request against a Servicenow API.

        Args:
            entity: The specific entity to make the request against.
            params: Query parameters for the REST API.
            path_url: The table path url for the ServiceNow API.

        Returns:
            The JSON response from the Servicenow REST API or the API request error details if an error occurs during the API call.
        """

        if params is None:
            params = {"sysparm_query": "ORDERBYDESCsys_updated_on"}
        else:
            existing_query = params.get("sysparm_query", "")
            if existing_query:
                params["sysparm_query"] = f"{existing_query}^ORDERBYDESCsys_updated_on"
            else:
                params["sysparm_query"] = "ORDERBYDESCsys_updated_on"
        effective_path = path_url if path_url else self.path_url
        url = f"{self.base_url}/api/{effective_path}/{entity}"
        response: requests.Response | None = None

        try:
            response = requests.get(
                url=url,
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            result = response.json()
            if len(result.get("result", [])) == 0:
                return no_data_in_get_request(response=response)

        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        return result

    def post_request(
        self,
        entity: str,
        payload: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
        files: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a generic POST request against the Servicenow API.

        Args:
            entity: The specific entity to make the request against.
            payload: A dictionary containing the input payload to be sent as JSON.
            data: A dictionary containing the input payload to be sent as form data.
            params: A dictionary containing the request params (Optional).
            headers: A dictionary containing the request headers (Optional).
            files: Files to upload as part of the request (used with form-data)

        Returns:
            The JSON response from the Servicenow API or the API request error details if an error occurs during the API call.
        """
        if payload and data:
            return ErrorDetails(
                status_code=None,
                url=None,
                reason="Cannot provide both 'payload' (for json) and 'data' (for form-data).",
                details=None,
                recommendation="Provide either payload or data",
            )

        request_headers = headers if headers is not None else self.headers

        # If entity contains '/', treat it as a full path from 'api/'.
        # Otherwise, use the default self.path_url.
        path = entity if "/" in entity else f"{self.path_url}/{entity}"
        url = f"{self.base_url}/api/{path}"
        response: requests.Response | None = None

        try:
            response = requests.post(
                url=url,
                headers=request_headers,
                json=payload,
                data=data,
                params=params,
                files=files,
            )
            response.raise_for_status()
            result = response.json()
            if "status_code" not in result:
                result["status_code"] = response.status_code
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        return result

    def delete_request(
        self, entity: str, entity_id: str, payload: Optional[dict[str, Any]] = None
    ) -> int | ErrorDetails:
        """
        Executes a generic delete request against the Servicenow API.

        Args:
            entity: The specific entity to make the request against.
            entity_id: The specific entity id to make delete the request against.
            payload: A dictionary containing the input payload (Optional).

        Returns:
            The status code of the request or the API request error details if an error occurs during the API call.
        """
        url = f"{self.base_url}/api/{self.path_url}/{entity}/{entity_id}"
        response: requests.Response | None = None

        try:
            response = requests.delete(
                url=url,
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.status_code

        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        return result

    def patch_request(
        self,
        entity: str,
        entity_id: str,
        payload: dict[str, Any],
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a generic upsert request against the Servicenow API.

        Args:
            entity: The specific entity to make the request against.
            entity_id: The specific entity id to make patch the request against.
            payload: A dictionary containing the input payload.
            params: A dictionary containing the request params (Optional).

        Returns:
            The JSON response from the Servicenow API or the API request error details if an error occurs during the API call.
        """
        url = f"{self.base_url}/api/{self.path_url}/{entity}/{entity_id}"
        response: requests.Response | None = None

        try:
            response = requests.patch(
                url=url,
                headers=self.headers,
                json=payload,
                params=params,
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


def get_servicenow_client() -> ServiceNowClient | ErrorDetails:
    """
    Get the servicenow client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the Servicenow client or the error details object if an error occurs while initializing the client and its credentials.
    """
    try:
        credentials = get_tool_credentials(Systems.SERVICENOW)
        servicenow_client = ServiceNowClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
        )

    except (AssertionError, ValueError, KeyError, requests.exceptions.RequestException) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during ServiceNow client initialization:{str(e)}",
            details=f"Caught error during ServiceNow client initialization:{str(e)}",
            recommendation=None,
        )

    return servicenow_client
