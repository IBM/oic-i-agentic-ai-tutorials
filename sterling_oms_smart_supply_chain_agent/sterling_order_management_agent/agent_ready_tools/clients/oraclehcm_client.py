# Standard library imports
from http import HTTPStatus
from typing import Any, Dict, Optional

# Third-party library imports
import requests
from requests.auth import HTTPBasicAuth

# wxo-domains
from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    handling_exceptions,
    no_data_in_get_request,
)
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class OracleHCMClient:
    """A remote client for Oracle HCM."""

    REST_FRAMEWORK_VERSION = "4"

    def __init__(self, base_url: str, username: str, password: str, version: str = "11.13.18.05"):
        """
        Args:
            base_url: The base URL for the Oracle HCM API.
            username: The username to use for authentication against the Oracle HCM API.
            password: The password to use for authentication against the Oracle HCM API.
            version: The version of Oracle HCM API.
        """
        self.base_url = base_url
        self.auth = HTTPBasicAuth(username, password)
        self.version = version

    def get_request(
        self,
        entity: str,
        q_expr: Optional[str] = None,
        expand_expr: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        finder_expr: Optional[str] = None,
        path: Optional[str] = "hcmRestApi",
        params: Optional[Dict[str, Any]] = None,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a GET request against the provided entity.

        Args:
            entity: The entity to query.
            q_expr: An optional q expression to restrict the results.
            expand_expr: An optional expand expression specifying which fields to expand.
            headers: An optional headers which are required for API request.
            finder_expr: An optional finder expression to search the collection.
            path: An optional path value that is used to called list of values apis.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the Oracle HCM API or the API request error details if an error occurs during the API call.
        """
        url = f"{self.base_url}/{path}/resources/{self.version}/{entity}"

        if params is None:
            params = {"links": "self"}
        else:
            params["links"] = "self"

        if q_expr is not None:
            params["q"] = q_expr
        if expand_expr is not None:
            params["expand"] = expand_expr
        if finder_expr is not None:
            params["finder"] = finder_expr
        if headers is None:
            headers = {}
        response: requests.Response | None = None
        try:
            response = requests.get(url=url, auth=self.auth, params=params, headers=headers)
            response.raise_for_status()
            json_response = response.json()
            if not json_response or ("items" in json_response and not json_response["items"]):
                return no_data_in_get_request(response=response)
            return json_response
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def post_request(
        self,
        entity: str,
        payload: dict[str, Any],
        params: Optional[dict[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a generic upsert request against the Oracle HCM API.

        Args:
            entity: The sub-directory entity of the resource to request.
            payload: A dictionary containing the input payload.
            params: A dictionary containing the request params (Optional).
            headers: A dictionary containing the request headers (Optional).

        Returns:
            The JSON response from the Oracle HCM API or the API request error details if an error occurs during the API call.
        """

        if headers is None:
            headers = {"REST-Framework-Version": self.REST_FRAMEWORK_VERSION}
        else:
            headers["REST-Framework-Version"] = self.REST_FRAMEWORK_VERSION
        url = f"{self.base_url}/hcmRestApi/resources/{self.version}/{entity}"
        response: requests.Response | None = None
        try:
            response = requests.post(
                url=url,
                auth=self.auth,
                json=payload,
                headers=headers,
                params=params,
            )

            response.raise_for_status()
            json_response = response.json()
            json_response["status_code"] = response.status_code
            return json_response
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def update_request(
        self, entity: str, payload: dict[str, Any] | str
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes the update request against the provided entity in Oracle HCM.

        Args:
            entity: The entity to query.
            payload: A dictionary containing the input payload.

        Returns:
            The JSON response from the Oracle HCM API or the API request error details if an error occurs during the API call.
        """

        url = f"{self.base_url}/hcmRestApi/resources/{self.version}/{entity}"

        headers = {"Content-Type": "application/json", "effective-Of": "RangeMode=UPDATE"}
        response: requests.Response | None = None
        try:
            response = requests.patch(url=url, json=payload, auth=self.auth, headers=headers)
            response.raise_for_status()
            json_response = response.json()
            json_response["status_code"] = response.status_code
            return json_response
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def put_request(
        self, entity: str, payload: dict[str, Any] | str
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes the HTTP PUT request to update an existing Oracle HCM resource identified by the
        given entity.

        Args:
            entity: The Oracle HCM resource to update.
            payload: The request body containing the fields to update for the given entity.

        Returns:
            The JSON response returned by the Oracle HCM API or the API request error details if an error occurs during the API call.
        """

        url = f"{self.base_url}/hcmRestApi/resources/{self.version}/{entity}"

        headers = {
            "Content-Type": "application/json",
            "effective-Of": "RangeMode=UPDATE",
        }
        response: requests.Response | None = None
        try:
            response = requests.put(url=url, json=payload, auth=self.auth, headers=headers)
            response.raise_for_status()
            if response.status_code == HTTPStatus.NO_CONTENT:
                return {
                    "status_code": response.status_code,
                }
            if "json" in response.headers.get("content-type", ""):
                result = response.json()
            else:
                result = {"raw_response": response.text}
            result["status_code"] = response.status_code
            return result
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def get_response_text(
        self,
        entity: str,
        headers: Optional[Dict[str, str]] = None,
        path: Optional[str] = "hcmRestApi",
    ) -> str | ErrorDetails:
        """
        Executes a GET request against the provided entity.

        Args:
            entity: The entity to query.
            headers: An optional headers which are required for API request.
            path: An optional path value that is used to called list of values apis.

        Returns:
            The text response from the Oracle HCM API or the API request error details if an error occurs during the API call.
        """
        url = f"{self.base_url}/{path}/resources/{self.version}/{entity}"

        if headers is None:
            headers = {}
        response: requests.Response | None = None
        try:
            response = requests.get(url=url, auth=self.auth, headers=headers)
            response.raise_for_status()
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)
        return response.text

    def delete_request(
        self,
        entity: str,
        headers: Optional[Dict[str, str]] = None,
        path: Optional[str] = "hcmRestApi",
    ) -> int | ErrorDetails:
        """
        Executes a DELETE request against the provided entity in Oracle HCM.

        Args:
            entity: The entity to query.
            headers: Optional headers input for API request, default to None.
            path: An optional path value that is used to called list of values apis.

        Returns:
            The status code from the Oracle HCM API or the API request error details if an error occurs during the API call.
        """
        url = f"{self.base_url}/{path}/resources/{self.version}/{entity}"

        if headers is None:
            headers = {}
        response: requests.Response | None = None
        try:
            response = requests.delete(url=url, auth=self.auth, headers=headers)
            response.raise_for_status()
            return response.status_code
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)


def get_oracle_hcm_client() -> OracleHCMClient | ErrorDetails:
    """
    Get the oracle hcm client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the Oracle HCM client or the error details if an error occurs while initializing the client and its credentials.
    """
    try:
        credentials = get_tool_credentials(Systems.ORACLE_HCM)
        oracle_client = OracleHCMClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            username=credentials[CredentialKeys.USERNAME],
            password=credentials[CredentialKeys.PASSWORD],
        )
    except (AssertionError, ValueError, KeyError, requests.exceptions.RequestException) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Oracle HCM client initialization:{str(e)}",
            details=f"Caught error during Oracle HCM client initialization:{str(e)}",
            recommendation=None,
        )
    return oracle_client
