import json
from typing import Any, List, Optional

import requests

from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    handling_exceptions,
    no_data_in_get_request,
)
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class Dynamics365Client:
    """A remote client for Dynamics 365."""

    def __init__(self, base_url: str, bearer_token: str):
        """
        Args:
            base_url: The base URL for the Dynamics 365 API.
            bearer_token: The bearer token fetched from wxo connection manager.
        """
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            "Accept": "application/json",
            "Prefer": "return=representation",
        }

    def get_request(
        self, api_version: str, entity: str, query_params: Optional[List[dict]] = None
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a GET request against a dynamics 365 API.

        Args:
            api_version: The specific version of the API, like "v1".
            entity: The specific category of the API, like "accounts".
            query_params: The Query parameters for the REST API.

        Returns:
            The JSON response from the Dynamics 365 REST API.
        """
        url = f"{self.base_url}/api/data/{api_version}/{entity}"  # ie: https://org69dba6c4.api.crm.dynamics.com/api/data/v9.1/accounts
        response: requests.Response | None = None
        if query_params:
            params: list[str] = []
            for f in query_params:
                assert isinstance(f, dict), f"filter parameter was not a dictionary."
                field = f.get("field")
                operator = f.get("operator")
                value = f.get("value")

                filter_string = ""

                if operator == "eq":
                    filter_string = (
                        f"{field} eq {repr(value)}"
                        if isinstance(value, (int, float, bool))
                        else f"{field} eq '{value}'"
                    )
                elif operator == "ne":
                    filter_string = (
                        f"{field} ne {repr(value)}"
                        if isinstance(value, (int, float, bool))
                        else f"{field} ne '{value}'"
                    )
                elif operator == "gt":
                    filter_string = (
                        f"{field} gt {repr(value)}"
                        if isinstance(value, (int, float, bool))
                        else f"{field} gt '{value}'"
                    )
                elif operator == "lt":
                    filter_string = (
                        f"{field} lt {repr(value)}"
                        if isinstance(value, (int, float, bool))
                        else f"{field} lt '{value}'"
                    )
                elif operator == "contains":
                    filter_string = f"contains({field},%27{value}%27)"

                params.append(filter_string)

            query_string = "?$filter=" + " and ".join(params) if params else ""
            url += f"{query_string}"

        try:
            response = requests.get(url=url, headers=self.headers)
            response.raise_for_status()
            json_response = response.json()
            if not json_response.get("value", None):
                return no_data_in_get_request(response=response)
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        return json_response

    def post_request(
        self,
        entity: str,
        api_version: str,
        data: dict,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a POST request to DYNAMICS API.

        Args:
            entity: The specific category of the API, like "accounts".
            api_version: The specific version of the API, like "v9.1".
            data: The Input data request.

        Returns:
            The JSON response from the dynamics365 REST API.
        """
        request_url = f"{self.base_url}/api/data/{api_version}/{entity}"
        response: requests.Response | None = None
        try:
            response = requests.post(
                url=request_url,
                headers=self.headers,
                data=json.dumps(data),
            )
            response.raise_for_status()
            json_response = response.json()
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=request_url)
        return json_response

    def patch_request(
        self, api_version: str, entity: str, record_id: str, data: dict
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a PATCH request against Dynamics 365 API.

        Args:
            api_version: Specific api_version.
            entity: The specific resource to make the request against.
            id: The GUID (ID) of the record to update.
            data: A dictionary containing ONLY the fields and values you want to update.

        Returns:
            The JSON response from the dynamics365 REST API.
        """

        request_url = f"{self.base_url}/api/data/{api_version}/{entity}({record_id})"
        response: requests.Response | None = None
        try:
            response = requests.patch(request_url, headers=self.headers, data=json.dumps(data))
            response.raise_for_status()
            json_response = response.json()
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=request_url)
        return json_response


def get_dynamics365_client() -> Dynamics365Client | ErrorDetails:
    """
    Get the dynamics 365 client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the dynamics 365 client.
    """
    credentials = get_tool_credentials(Systems.DYNAMICS365)
    try:
        dynamics365_client = Dynamics365Client(
            base_url=credentials[CredentialKeys.BASE_URL],
            bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
        )
    except (AssertionError, ValueError, requests.exceptions.RequestException) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Dynamics 365 client initialization:{str(e)}",
            details=f"Caught error during Dynamics 365 client initialization:{str(e)}",
            recommendation=None,
        )
    return dynamics365_client
