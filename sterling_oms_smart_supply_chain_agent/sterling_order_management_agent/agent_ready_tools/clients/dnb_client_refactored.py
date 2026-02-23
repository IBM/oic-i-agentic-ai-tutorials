import json
from typing import Any, Optional

import requests

from agent_ready_tools.clients.clients_enums import DNBEntitlements
from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    extract_error_details_sales_dnb,
    handling_exceptions,
    no_data_in_get_request,
)
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class DNBClient:
    """A remote client for DNB."""

    def __init__(self, base_url: str, bearer_token: str, domain: DNBEntitlements):
        """
        Args:
            base_url: The base URL for the DNB API.
            bearer_token: The bearer token fetched from wxo connection manager.
            domain: the wxo domain.
        """
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        }
        self.domain = domain

    def get_request(
        self,
        version: str,
        category: str,
        endpoint: Optional[str] = None,
        path_parameter: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
        search_key: Optional[str] = None,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a GET request against a DnB API.

        Args:
            version: The specific version of the API, like "v1".
            category: The specific category of the API, like "search".
            endpoint: The specific endpoint to make the request against, like "competitors".
            path_parameter: The path parameter for the REST API.
            params: The Query parameters for the REST API.
            search_key: The field in the API response that should be checked for the presence of data.

        Returns:
            The JSON response from the DnB REST API.
        """
        url = f"{self.base_url}/{version}/{category}"
        response: requests.Response | None = None
        if endpoint:
            url += f"/{endpoint}"
        if path_parameter:
            url += f"/{path_parameter}"
        try:
            response = requests.get(
                url=url,
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            json_response = response.json()
            if search_key and not json_response.get(search_key, None):
                return no_data_in_get_request(response=response)
            return json_response
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            if response is not None:
                if self.domain == DNBEntitlements.SALES:
                    return extract_error_details_sales_dnb(
                        response=response, api_url=url, url_params=params
                    )
                else:
                    return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def post_request(
        self,
        endpoint: str,
        category: str,
        data: dict,
        version: str,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a POST request against a DnB API.

        Args:
            endpoint: The specific endpoint to make the request against, like "criteria".
            category: The specific category of the API, like "search".
            data: The Input data request.
            version: The specific version of the API, like "v1".

        Returns:
            The JSON response from the DnB REST API.
        """
        url = f"{self.base_url}/{version}/{category}/{endpoint}"
        response: requests.Response | None = None
        try:
            response = requests.post(
                url=url,
                headers=self.headers,
                data=json.dumps(data),
            )
            json_response = response.json()
            return json_response
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            if response is not None:
                if self.domain == DNBEntitlements.SALES:
                    return extract_error_details_sales_dnb(
                        response=response, api_url=url, url_params=data
                    )
                else:
                    return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)


def get_dnb_client(entitlement: DNBEntitlements) -> DNBClient | ErrorDetails:
    """
    Get the dnb client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Args:
        entitlement: the credential entitlement (e.g. sales, procurement)

    Returns:
        A new instance of the DnB client.
    """
    credentials = get_tool_credentials(Systems.DNB, sub_category=entitlement)
    try:
        dnb_client = DNBClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
            domain=entitlement,
        )
    except (AssertionError, ValueError, requests.exceptions.RequestException) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during DNB client initialization:{str(e)}",
            details=f"Caught error during DNB client initialization:{str(e)}",
            recommendation=None,
        )
    return dnb_client
