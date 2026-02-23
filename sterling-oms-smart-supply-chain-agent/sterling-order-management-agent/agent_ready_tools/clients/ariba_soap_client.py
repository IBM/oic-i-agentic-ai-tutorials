from typing import Optional

import requests
from requests.auth import HTTPBasicAuth

from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class AribaSOAPClient:
    """A remote client for SAP Ariba SOAP endpoints."""

    def __init__(
        self,
        base_url: str,
        realm: str,
        username: str,
        password: str,
        requester_password: str,
    ):
        """
        Args:
            requester_password: password adapter for requester
            base_url: The base URL for the Ariba SOAP API.
            realm: The realm of the endpoint connection to Ariba API
            username: The username to use for authentication against the Ariba API.
            password: The password to use for authentication against the Ariba API.
        """
        self.base_url = base_url
        self.username = username
        self.password = password
        self.realm = realm
        self.requester_password = requester_password

    def post_request(
        self,
        endpoint: str,
        payload: Optional[bytes] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> requests.Response:
        """
        Executes a POST request against SAP Ariba API.

        Args:
            endpoint: The endpoint to query.
            payload: Byte string representing the request payload. If provided, this bytes object
                contains the raw data to be sent. Defaults to None when no payload is given.
            headers: A dictionary containing the request headers (Optional).

        Returns:
            The XML response from the SAP Ariba API.
        """
        url = f"{self.base_url}/{endpoint}"

        # Creating auth object to get the basic authorization token to be passed in the request
        auth_object = HTTPBasicAuth(self.username, self.password)
        xml_response = requests.post(url=url, data=payload, headers=headers, auth=auth_object)
        xml_response.raise_for_status()
        return xml_response


def get_ariba_soap_client() -> AribaSOAPClient:
    """
    Get the Ariba SOAP client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of AribaClient.
    """
    credentials = get_tool_credentials(system=Systems.ARIBA_SOAP)
    ariba_soap_client = AribaSOAPClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        realm=credentials[CredentialKeys.REALM],
        username=credentials[CredentialKeys.USERNAME],
        password=credentials[CredentialKeys.PASSWORD],
        requester_password=credentials[CredentialKeys.REQUESTER_PASSWORD],
    )
    return ariba_soap_client
