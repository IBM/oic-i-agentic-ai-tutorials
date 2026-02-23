from http import HTTPMethod
from typing import Any, Dict, List, Optional

import requests

from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    handling_exceptions,
)
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems

DEFAULT_SCOPE = [
    "crm.dealsplits.read_write",
    "crm.export",
    "crm.import",
    "crm.lists.read",
    "crm.lists.write",
    "crm.objects.appointments.read",
    "crm.objects.appointments.write",
    "crm.objects.carts.read",
    "crm.objects.carts.write",
    "crm.objects.commercepayments.read",
    "crm.objects.commercepayments.write",
    "crm.objects.companies.read",
    "crm.objects.companies.write",
    "crm.objects.contacts.read",
    "crm.objects.contacts.write",
    "crm.objects.courses.read",
    "crm.objects.courses.write",
    "crm.objects.custom.read",
    "crm.objects.custom.write",
    "crm.objects.deals.read",
    "crm.objects.deals.write",
    "crm.objects.feedback_submissions.read",
    "crm.objects.goals.read",
    "crm.objects.goals.write",
    "crm.objects.invoices.read",
    "crm.objects.invoices.write",
    "crm.objects.leads.read",
    "crm.objects.leads.write",
    "crm.objects.line_items.read",
    "crm.objects.line_items.write",
    "crm.objects.listings.read",
    "crm.objects.listings.write",
    "crm.objects.marketing_events.read",
    "crm.objects.marketing_events.write",
    "crm.objects.orders.read",
    "crm.objects.orders.write",
    "crm.objects.owners.read",
    "crm.objects.partner-clients.read",
    "crm.objects.partner-clients.write",
    "crm.objects.partner-services.read",
    "crm.objects.partner-services.write",
    "crm.objects.products.read",
    "crm.objects.products.write",
    "crm.objects.quotes.read",
    "crm.objects.quotes.write",
    "crm.objects.services.read",
    "crm.objects.services.write",
    "crm.objects.subscriptions.read",
    "crm.objects.subscriptions.write",
    "crm.objects.users.read",
    "crm.objects.users.write",
    "crm.pipelines.orders.read",
    "crm.pipelines.orders.write",
    "crm.schemas.appointments.read",
    "crm.schemas.appointments.write",
    "crm.schemas.carts.read",
    "crm.schemas.carts.write",
    "crm.schemas.commercepayments.read",
    "crm.schemas.commercepayments.write",
    "crm.schemas.companies.read",
    "crm.schemas.companies.write",
    "crm.schemas.contacts.read",
    "crm.schemas.contacts.write",
    "crm.schemas.courses.read",
    "crm.schemas.courses.write",
    "crm.schemas.custom.read",
    "crm.schemas.deals.read",
    "crm.schemas.deals.write",
    "crm.schemas.invoices.read",
    "crm.schemas.invoices.write",
    "crm.schemas.line_items.read",
    "crm.schemas.listings.read",
    "crm.schemas.listings.write",
    "crm.schemas.orders.read",
    "crm.schemas.orders.write",
    "crm.schemas.quotes.read",
    "crm.schemas.services.read",
    "crm.schemas.services.write",
    "crm.schemas.subscriptions.read",
    "crm.schemas.subscriptions.write",
    "oauth",
]


class HubSpotClient:
    """A remote client for HubSpot."""

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
        scope: Optional[List[str]] = None,
    ):
        """
        Args:
            base_url: The base URL for the HubSpot API.
            bearer_token: The bearer token.
        """
        self.base_url = base_url
        self.bearer_token = bearer_token
        self.headers = {
            "Content-Type": "application/json",
        }
        self.scope = DEFAULT_SCOPE if scope is None else scope

    def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        get_content: Optional[bool] = False,
    ) -> dict[str, Any] | ErrorDetails:
        """Makes a <method> request to the given URL with the given params and payload."""

        self.headers["Authorization"] = f"Bearer {self.bearer_token}"
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

            if method == HTTPMethod.DELETE:
                return {"status_code": response.status_code}

            if method == HTTPMethod.GET and get_content:
                return {"text": response.text, "headers": response.headers}

            response_json = response.json()

            if response_json.get("status") == "error":
                error_details = extract_error_details(response=response)
                error_details.details = response_json.get("message", error_details.details)
                return error_details

        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        return response_json

    def delete_request(
        self,
        entity: str,
        version: str,
        service: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> int | ErrorDetails:
        """
        Executes a DELETE request against HubSpot API.

        Args:
            entity: The specific entity to make the request against.
            version: The specific version of the API.
            service: The HubSpot API service to use (e.g., "crm", "cms", "automation).
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            The response status code from the HubSpot REST API
            or the API request error details if an error occurs during the API call.
        """

        response = self._request(
            HTTPMethod.DELETE,
            url=f"{self.base_url}/{service}/{version}/{entity}",
            payload=payload,
            params=params,
        )
        if isinstance(response, ErrorDetails):
            return response
        return response["status_code"]

    def patch_request(
        self,
        service: str,
        version: str,
        entity: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any] | ErrorDetails:
        """
        Executes a PATCH request against HubSpot API.

        Args:
            service: The HubSpot API service to use (e.g., "crm", "cms", "automation).
            version: The specific version of the API.
            entity: The specific entity to make the request against.
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            The JSON response from the HubSpot REST API
            or the API request error details if an error occurs during the API call.
        """
        response = self._request(
            HTTPMethod.PATCH,
            url=f"{self.base_url}/{service}/{version}/{entity}",
            payload=payload,
            params=params,
        )
        return response

    def put_request(
        self,
        service: str,
        version: str,
        entity: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any] | ErrorDetails:
        """
        Executes a PUT request against HubSpot API.

        Args:
            service: The HubSpot API service to use (e.g., "crm", "cms", "automation).
            version: The specific version of the API.
            entity: The specific entity to make the request against.
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            The JSON response from the HubSpot REST API
            or the API request error details if an error occurs during the API call.
        """
        response = self._request(
            HTTPMethod.PUT,
            url=f"{self.base_url}/{service}/{version}/{entity}",
            payload=payload,
            params=params,
        )
        return response

    def post_request(
        self,
        service: str,
        version: str,
        entity: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any] | ErrorDetails:
        """
        Executes a POST request against HubSpot API.

        Args:
            service: The HubSpot API service to use (e.g., "crm", "cms", "automation).
            version: The specific version of the API.
            entity: The specific entity to make the request against.
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            The JSON response from the HubSpot REST API
            or the API request error details if an error occurs during the API call.
        """
        response = self._request(
            HTTPMethod.POST,
            url=f"{self.base_url}/{service}/{version}/{entity}",
            payload=payload,
            params=params,
        )
        return response

    def get_request(
        self,
        service: str,
        version: str,
        entity: str,
        params: Optional[dict[str, Any]] = None,
        content: Optional[bool] = False,
    ) -> Dict[str, Any] | ErrorDetails:
        """
        Executes a GET request against HubSpot API.

        Args:
            service: The HubSpot API service to use (e.g., "crm", "cms", "automation).
            version: The specific version of the API.
            entity: The specific entity to make the request against.
            params: Query parameters for the REST API.
            content: This is optional parameter to retrieve the file content as text. Defaults to False.

        Returns:
            The JSON response from the HubSpot REST API
            or the API request error details if an error occurs during the API call.
        """

        response = self._request(
            HTTPMethod.GET,
            url=f"{self.base_url}/{service}/{version}/{entity}",
            params=params,
            get_content=content,
        )
        return response


def get_hubspot_client() -> HubSpotClient | ErrorDetails:
    """
    Get the HubSpot client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the HubSpot client
        or the error details object if an error occurs while initalizing the client and its credentials.
    """
    try:
        credentials = get_tool_credentials(Systems.HUBSPOT)
        hubspot_client = HubSpotClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
        )
    except (
        AssertionError,
        ValueError,
        requests.exceptions.RequestException,
    ) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Hubspot client initialization:{str(e)}",
            details=f"Caught error during Hubspot client initialization:{str(e)}",
            recommendation=None,
        )
    return hubspot_client
