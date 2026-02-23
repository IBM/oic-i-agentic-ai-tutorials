import json
from typing import Any, Dict, List, Optional, Union

import requests
from requests.exceptions import RequestException

from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


def _get_ibm_sip_tenant_id_from_url(server_url: str) -> str:
    """
    Temp workaround to get tenant_id from server_url for IBM SIP connections to avoid a secondary
    key_value conn, static.

    Args:
        server_url: The server_url (base_url) for IBM SIP APIs.

    Returns:
        IBM SIP tenant id.
    """
    # TODO: remove IBM SIP tenant_name hack once custom keys in connection credentials are supported
    # this hack requires that the 'server_url' field value supplied in the connection/credentials be in the format:
    # 'https://api.watsoncommerce.ibm.com/<tenant_name>'
    server_url_parts = server_url.split("/")
    assert server_url_parts, f"Expected server URL not found in '{Systems.IBM_SIP}' connection."
    assert (
        len(server_url_parts) > 1
        and server_url_parts[len(server_url_parts) - 1]
        and "api.watsoncommerce.ibm.com" in server_url_parts[len(server_url_parts) - 2]
    ), (
        f"Unexpected server URL format in '{Systems.IBM_SIP}' connection: '{server_url}'. "
        f"Expected format: 'https://api.watsoncommerce.ibm.com/<tenant_name>'"
    )
    return server_url_parts[len(server_url_parts) - 1]


class IBMSIPClient:
    """A remote client for IBM Sterling Intelligent Promising."""

    def __init__(self, base_url: str, bearer_token: str):
        """
        Args:
            base_url: The base URL for IBM SIP API.
            bearer_token: The bearer token fetched from wxo connection manager.
        """
        # NOTE: base url is actually `{base_url}/{tenant_id}`
        self.tenant_id = _get_ibm_sip_tenant_id_from_url(base_url)
        # clean base_url for downstream use
        self.base_url = base_url.removesuffix("/" + self.tenant_id)
        self.headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def delete_request(
        self,
        resource_name: str,
        api_category: str = "inventory",
        params: Optional[dict[str, Any]] = None,
    ) -> Union[int, Dict[str, Any]]:
        """
        Executes a DELETE request against IBM SIP API.

        Args:
            resource_name: The specific resource to make the request against.
            api_category: The specific API category (e.g. "inventory", "catalog")
            params: Query parameters for the REST API.

        Returns:
            HTTP status code on success, or an error dictionary on failure.
        """
        if params is None:
            params = {}

        try:
            response = requests.delete(
                url=f"{self.base_url}/{api_category}/{self.tenant_id}/{resource_name}",
                headers=self.headers,
                params=json.dumps(params),
            )
            response.raise_for_status()
            return response.status_code
        except RequestException:
            try:
                return response.json()
            except ValueError:
                # Handle the case where response content is not JSON
                return {
                    "errorMessage": response.text,
                    "status_code": response.status_code,
                }

    def patch_request(
        self,
        resource_name: str,
        api_category: str = "inventory",
        payload: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a PATCH request against IBM SIP API.

        Args:
            resource_name: The specific resource to make the request against.
            api_category: The specific API category (e.g. "inventory", "catalog")
            payload: The request payload.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the IBM Sterling Promising REST API.
        """
        if params is None:
            params = {}
        if payload is None:
            payload = {}

        try:
            response = requests.patch(
                url=f"{self.base_url}/{api_category}/{self.tenant_id}/{resource_name}",
                headers=self.headers,
                params=params,
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except RequestException:
            try:
                return response.json()
            except ValueError:
                # Handle the case where response content is not JSON
                return {
                    "errorMessage": response.text,
                    "status_code": response.status_code,
                }

    def post_request(
        self,
        resource_name: str,
        api_category: str = "inventory",
        params: Optional[dict[str, Any]] = None,
        payload: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a POST request against IBM SIP API.

        Args:
            resource_name: The specific resource to make the request against.
            api_category: The specific API category (e.g. "inventory", "catalog")
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            The JSON response from the IBM SIP REST API.
        """
        if params is None:
            params = {}

        try:
            response = requests.post(
                url=f"{self.base_url}/{api_category}/{self.tenant_id}/{resource_name}",
                headers=self.headers,
                params=params,
                data=json.dumps(payload),
            )
            response.raise_for_status()
            return response.json()
        except RequestException:
            try:
                return response.json()
            except ValueError:
                # Handle the case where response content is not JSON
                return {
                    "errorMessage": response.text,
                    "status_code": response.status_code,
                }

    def put_request(
        self,
        resource_name: str,
        api_category: str = "inventory",
        params: Optional[dict[str, Any]] = None,
        payload: Union[Optional[dict[str, Any]], list[dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a PUT request against IBM SIP API.

        Args:
            resource_name: The specific resource to make the request against.
            api_category: The specific API category (e.g. "inventory", "catalog")
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            The JSON response from the IBM SIP REST API.
        """
        if params is None:
            params = {}

        try:
            response = requests.put(
                url=f"{self.base_url}/{api_category}/{self.tenant_id}/{resource_name}",
                headers=self.headers,
                params=params,
                data=json.dumps(payload),
            )
            response.raise_for_status()
            return response.json()
        except RequestException:
            try:
                return response.json()
            except ValueError:
                # Handle the case where response content is not JSON
                return {
                    "errorMessage": response.text,
                    "status_code": response.status_code,
                }

    def get_request(
        self,
        resource_name: str,
        api_category: str = "inventory",
        params: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a GET request against IBM SIP API.

        Args:
            resource_name: The specific resource to make the request against.
            api_category: The specific API category (e.g. "inventory", "catalog")
            params: Query parameters for the REST API.

        Returns:
            The JSON list response from the IBM SIP REST API.
        """
        if params is None:
            params = {}

        try:
            response = requests.get(
                url=f"{self.base_url}/{api_category}/{self.tenant_id}/{resource_name}",
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except RequestException:
            try:
                return response.json()
            except ValueError:
                # Handle the case where response content is not JSON
                return {
                    "errorMessage": response.text,
                    "status_code": response.status_code,
                }


def get_ibm_sip_client() -> IBMSIPClient:
    """
    Get the IBM Sterling Intelligent Promising client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the WatsonCommerce client.
    """
    credentials = get_tool_credentials(Systems.IBM_SIP)
    ibm_sip_client = IBMSIPClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
    )
    return ibm_sip_client
