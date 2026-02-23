from typing import Any, Dict, List, Optional

import requests
from requests.exceptions import RequestException

from agent_ready_tools.clients.clients_enums import AribaApplications
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class AribaClient:
    """A remote client for ariba."""

    def __init__(
        self,
        base_url: str,
        token_url: str,
        ariba_realm: str,
        client_id: str,
        client_secret: str,
        api_key: str,
        buyer_anid: str,
        password_adapter: str,
        app_name: str,
    ):
        """
        Args:
            base_url: The base URL for the ariba API.
            token_url: The OAuth URL for generating bearer token.
            ariba_realm: A unique instance segregating data and configurations in ariba.
            client_id: The client id to authenticate with.
            client_secret: The client secret to authenticate with.
            api_key: The api key for the application to pass in headers.
            buyer_anid: The buyer anid to pass in headers
            password_adapter: The password adapter configured in Ariba
            app_name: Ariba application name
        """
        self.base_url = base_url
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.ariba_realm = ariba_realm
        self.buyer_anid = buyer_anid
        self.password_adapter = password_adapter
        self.headers = {"apiKey": f"{api_key}"}
        self.bearer_token = self.get_ariba_token()
        self.api_key = api_key
        self.app_name = app_name
        assert self.bearer_token

    def post_request(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a POST request against ariba API.

        Args:
            endpoint: end point for the API
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            The JSON response from the ariba REST API.
        """

        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "apiKey": self.headers["apiKey"],
            "Content-Type": "application/json",
        }
        if params is None:
            params = {"realm": f"{self.ariba_realm}"}
        else:
            params["realm"] = f"{self.ariba_realm}"

        url = f"{self.base_url}/api/{endpoint}"

        response = None
        try:

            response = requests.post(url=url, json=payload, headers=headers, params=params)

            response.raise_for_status()
            return response.json()
        except RequestException:
            if response is not None:
                try:
                    error_json = response.json()  # if JSON response
                except ValueError:
                    # handle the case where response content is not JSON
                    status_code = getattr(response, "status_code", "Unknown")
                    error_json = {
                        "message": f"Non-JSON response receive status code: {status_code}",
                    }
            else:
                # connection error, timeout, etc.
                error_json = {
                    "message": "No response received (request failed before getting a response)"
                }

            return error_json

    def post_request_list(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes a POST request against ariba API.

        Args:
            endpoint: end point for the API
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            The JSON response from the ariba REST API.
        """

        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "apiKey": self.headers["apiKey"],
            "Content-Type": "application/json",
        }
        if params is None:
            params = {"realm": f"{self.ariba_realm}"}
        else:
            params["realm"] = f"{self.ariba_realm}"

        url = f"{self.base_url}/api/{endpoint}"
        response = None
        try:

            response = requests.post(url=url, json=payload, headers=headers, params=params)

            response.raise_for_status()
            return response.json()
        except RequestException:
            if response is not None:
                try:
                    error_json = response.json()  # if JSON response
                except ValueError:
                    # handle the case where response content is not JSON
                    status_code = getattr(response, "status_code", "Unknown")
                    error_json = {
                        "message": f"Non-JSON response receive status code: {status_code}",
                    }
            else:
                # connection error, timeout, etc.
                error_json = {
                    "message": "No response received (request failed before getting a response)"
                }

            return error_json

    def get_request(self, endpoint: str, params: Optional[dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a GET request against ariba API.

        Args:
            endpoint: end point for the API
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the ariba REST API.
        """

        # common headers
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "apiKey": self.headers["apiKey"],
            "Content-Type": "application/json",
        }

        # additional headers for Master Data Retrieval API
        if self.app_name == AribaApplications.MASTER_DATA_RETRIEVAL:
            headers["X-Realm"] = self.ariba_realm
            headers["Accept-Language"] = "en"

        # additonal headers for Ariba Network API
        if self.buyer_anid:
            headers["X-ARIBA-NETWORK-ID"] = self.buyer_anid

        url = f"{self.base_url}/api/{endpoint}"

        response = None
        try:

            response = requests.get(url=url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except RequestException:
            if response is not None:
                try:
                    error_json = response.json()  # if JSON response
                except ValueError:
                    # handle the case where response content is not JSON
                    status_code = getattr(response, "status_code", "Unknown")
                    error_json = {
                        "message": f"Non-JSON response receive status code: {status_code}",
                    }
            else:
                # connection error, timeout, etc.
                error_json = {
                    "message": "No response received (request failed before getting a response)"
                }
            return error_json

    def get_request_list(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes a GET request against ariba API.

        Args:
            endpoint: end point for the API
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the ariba REST API.
        """

        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "apiKey": self.headers["apiKey"],
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/api/{endpoint}"

        if params is None:
            params = {"realm": f"{self.ariba_realm}"}
        else:
            params["realm"] = f"{self.ariba_realm}"

        response = None
        try:

            response = requests.get(url=url, params=params, headers=headers)

            response.raise_for_status()
            return response.json()
        except RequestException:
            if response is not None:
                try:
                    error_json = response.json()  # if JSON response
                except ValueError:
                    # handle the case where response content is not JSON
                    status_code = getattr(response, "status_code", "Unknown")
                    error_json = {
                        "message": f"Non-JSON response receive status code: {status_code}",
                    }
            else:
                # connection error, timeout, etc.
                error_json = {
                    "message": "No response received (request failed before getting a response)"
                }

            return error_json

    def patch_request(
        self,
        endpoint: str,
        payload: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a PATCH request against ariba API.

        Args:
            endpoint: end point for the API
            payload: The request payload.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the ariba REST API.
        """

        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "apiKey": self.headers["apiKey"],
            "Content-Type": "application/json",
        }
        if params is None:
            params = {"realm": f"{self.ariba_realm}"}
        else:
            params["realm"] = f"{self.ariba_realm}"

        url = f"{self.base_url}/api/{endpoint}"

        response = None
        try:

            response = requests.patch(url=url, json=payload, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except RequestException:
            if response is not None:
                try:
                    error_json = response.json()  # if JSON response
                except ValueError:
                    # handle the case where response content is not JSON
                    status_code = getattr(response, "status_code", "Unknown")
                    error_json = {
                        "message": f"Non-JSON response receive status code: {status_code}",
                    }
            else:
                # connection error, timeout, etc.
                error_json = {
                    "message": "No response received (request failed before getting a response)"
                }

            return error_json

    def delete_request(
        self,
        endpoint: str,
        payload: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> int:
        """
        Executes a DELETE request against ariba API.

        Args:
            endpoint: end point for the API
            payload: The request payload.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the ariba REST API.
        """
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "apiKey": self.headers["apiKey"],
            "Content-Type": "application/json",
        }
        if params is None:
            params = {"realm": f"{self.ariba_realm}"}
        else:
            params["realm"] = f"{self.ariba_realm}"

        url = f"{self.base_url}/api/{endpoint}"

        response = None
        try:

            response = requests.delete(url=url, json=payload, headers=headers, params=params)

            response.raise_for_status()
            return response.status_code
        except RequestException:
            if response is not None:
                try:
                    error_json = response.json()  # if JSON response
                except ValueError:
                    # handle the case where response content is not JSON
                    status_code = getattr(response, "status_code", "Unknown")
                    error_json = {
                        "message": f"Non-JSON response receive status code: {status_code}",
                    }
            else:
                # connection error, timeout, etc.
                error_json = {
                    "message": "No response received (request failed before getting a response)"
                }

            return error_json

    def get_ariba_token(self) -> str:
        """
        return: An access token for the specific scope(s).
        """

        token_url = f"{self.token_url}/v2/oauth/token"

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }

        # Make the POST request to obtain the token
        response = requests.post(token_url, headers=headers, data=payload)

        response_data = response.json()

        if "error" in response_data:
            message = response_data.get("description", "")
            return message

        if response.status_code == 200:
            bearer_token = response_data.get("access_token")

        return bearer_token


def get_ariba_client(application: AribaApplications) -> AribaClient:
    """
    Get the ariba client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Args:
        application: The specific application to get access token for in ariba procurement.

    Returns:
        A new instance of AribaClient.
    """
    credentials = get_tool_credentials(system=Systems.ARIBA, sub_category=application)
    ariba_client = AribaClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        token_url=credentials[CredentialKeys.TOKEN_URL],
        ariba_realm=credentials[CredentialKeys.REALM],
        client_id=credentials[CredentialKeys.CLIENT_ID],
        client_secret=credentials[CredentialKeys.CLIENT_SECRET],
        api_key=credentials[CredentialKeys.API_KEY],
        buyer_anid=credentials[CredentialKeys.BUYER_ANID],
        password_adapter=credentials[CredentialKeys.PASSWORD_ADAPTER],
        app_name=application,
    )
    return ariba_client
