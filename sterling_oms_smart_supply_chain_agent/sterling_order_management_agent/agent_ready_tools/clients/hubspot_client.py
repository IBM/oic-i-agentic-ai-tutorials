from http import HTTPMethod, HTTPStatus
from typing import Any, Dict, List, Optional

import requests

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
        token_url: str,
        client_id: str,
        client_secret: str,
        initial_bearer_token: str,
        initial_refresh_token: str,
        scope: Optional[List[str]] = None,
    ):
        """
        Args:
            base_url: The base URL for the HubSpot API.
            token_url: The URL for authentication tokens for the HubSpot API.
            client_id: The client ID authenticate with.
            client_secret: The client secret to authenticate with.
            initial_bearer_token: The initial bearer token from wxo-domains credentials file.
            initial_refresh_token: The initial refresh token from wxo-domains credentials file.
            scope: A list of scopes whish is used to get token for API requests.
        """
        self.base_url = base_url
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.initial_bearer_token = initial_bearer_token
        self.initial_refresh_token = initial_refresh_token
        self.headers = {
            "Content-Type": "application/json",
        }
        self.scope = DEFAULT_SCOPE if scope is None else scope
        self.bearer_token = self.get_hubspot_oauth_token()
        assert self.bearer_token

    def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """Makes a <method> request to the given URL with the given params and payload."""
        for _ in range(2):  # 1 retry
            self.headers["Authorization"] = f"Bearer {self.bearer_token}"
            response = requests.request(
                method=method,
                url=url,
                params=params,
                headers=self.headers,
                json=payload,
            )
            if response.status_code == HTTPStatus.UNAUTHORIZED:
                self.bearer_token = self.get_hubspot_oauth_token()
            else:
                break

        return response

    def get_hubspot_oauth_token(self) -> str:
        """
        Returns:
            An access token for the specific scope(s).
        """

        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.initial_refresh_token,
            "scope": " ".join(self.scope),
        }

        headers = {
            "Content-type": "application/x-www-form-urlencoded",
            "Accept": "*/*",
        }

        # Make the POST request to obtain the token
        response = requests.post(
            self.token_url,
            headers=headers,
            data=payload,
        )

        response.raise_for_status()

        access_token = ""

        # Check if the request was successful
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data["access_token"]

        return access_token

    def delete_request(
        self,
        entity: str,
        version: str,
        service: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> int:
        """
        Executes a DELETE request against HubSpot API.

        Args:
            entity: The specific entity to make the request against.
            version: The specific version of the API.
            service: The HubSpot API service to use (e.g., "crm", "cms", "automation).
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            The JSON response from the HubSpot REST API.
        """

        response = self._request(
            HTTPMethod.DELETE,
            url=f"{self.base_url}/{service}/{version}/{entity}",
            payload=payload,
            params=params,
        )
        response.raise_for_status()
        return response.status_code

    def patch_request(
        self,
        service: str,
        version: str,
        entity: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a PATCH request against HubSpot API.

        Args:
            service: The HubSpot API service to use (e.g., "crm", "cms", "automation).
            version: The specific version of the API.
            entity: The specific entity to make the request against.
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            The JSON response from the HubSpot REST API.
        """
        response = self._request(
            HTTPMethod.PATCH,
            url=f"{self.base_url}/{service}/{version}/{entity}",
            payload=payload,
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def put_request(
        self,
        service: str,
        version: str,
        entity: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a PUT request against HubSpot API.

        Args:
            service: The HubSpot API service to use (e.g., "crm", "cms", "automation).
            version: The specific version of the API.
            entity: The specific entity to make the request against.
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            The JSON response from the HubSpot REST API.
        """

        response = self._request(
            HTTPMethod.PUT,
            url=f"{self.base_url}/{service}/{version}/{entity}",
            payload=payload,
            params=params,
        )

        response.raise_for_status()
        return response.json()

    def post_request(
        self,
        service: str,
        version: str,
        entity: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a POST request against HubSpot API.

        Args:
            service: The HubSpot API service to use (e.g., "crm", "cms", "automation).
            version: The specific version of the API.
            entity: The specific entity to make the request against.
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            The JSON response from the HubSpot REST API.
        """

        response = self._request(
            HTTPMethod.POST,
            url=f"{self.base_url}/{service}/{version}/{entity}",
            payload=payload,
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def get_request(
        self,
        service: str,
        version: str,
        entity: str,
        params: Optional[dict[str, Any]] = None,
        content: Optional[bool] = False,
    ) -> Dict[str, Any]:
        """
        Executes a GET request against HubSpot API.

        Args:
            service: The HubSpot API service to use (e.g., "crm", "cms", "automation).
            version: The specific version of the API.
            entity: The specific entity to make the request against.
            params: Query parameters for the REST API.
            content: This is optional parameter to retrieve the file content as text. Defaults to False.

        Returns:
            The JSON response from the HubSpot REST API.
        """

        response = self._request(
            HTTPMethod.GET,
            url=f"{self.base_url}/{service}/{version}/{entity}",
            params=params,
        )
        response.raise_for_status()
        if content:
            return {"text": response.text, "headers": response.headers}
        return response.json()


def get_hubspot_client() -> HubSpotClient:
    """
    Get the HubSpot client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the HubSpot client.
    """
    credentials = get_tool_credentials(Systems.HUBSPOT)
    hubspot_client = HubSpotClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        token_url=credentials[CredentialKeys.TOKEN_URL],
        client_id=credentials[CredentialKeys.CLIENT_ID],
        client_secret=credentials[CredentialKeys.CLIENT_SECRET],
        initial_bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
        initial_refresh_token=credentials[CredentialKeys.REFRESH_TOKEN],
    )
    return hubspot_client
