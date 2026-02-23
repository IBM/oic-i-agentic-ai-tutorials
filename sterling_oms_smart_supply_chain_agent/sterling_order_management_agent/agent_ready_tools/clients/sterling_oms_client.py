import base64
import json
from typing import Any, Dict, Optional, Union

from OpenSSL import crypto
import certifi
import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException
from urllib3.contrib.pyopenssl import PyOpenSSLContext  # pants: no-infer-dep
from urllib3.util.ssl_ import create_urllib3_context  # pants: no-infer-dep

from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class ClientSideCertificateHTTPAdapter(requests.adapters.HTTPAdapter):
    """An HTTP Adapter class to handle in-memory certificates."""

    DEFAULT_PROTOCOL = create_urllib3_context().protocol

    def __init__(
        self,
        cert_pem_str: str,
        key_pem_str: str,
        protocol: int = DEFAULT_PROTOCOL,
        *args: Any,
        **kwargs: Any,
    ):
        """Constructor method for HTTP Adapter with in-memory certificates."""
        # using encoded credentials now, need to decode them first now
        cert_bytes = base64.b64decode(cert_pem_str)
        cert_pem_str = cert_bytes.decode("utf-8")

        key_bytes = base64.b64decode(key_pem_str)
        key_pem_str = key_bytes.decode("utf-8")

        # Load certificate and private key from PEM strings in memory
        self._cert = crypto.load_certificate(
            crypto.FILETYPE_PEM,
            cert_pem_str.encode("utf-8") if isinstance(cert_pem_str, str) else cert_pem_str,
        )
        self._key = crypto.load_privatekey(
            crypto.FILETYPE_PEM,
            key_pem_str.encode("utf-8") if isinstance(key_pem_str, str) else key_pem_str,
        )
        self._protocol = protocol
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> Any:
        """Initiate the pool manager."""
        ctx = PyOpenSSLContext(self._protocol)
        kwargs["ssl_context"] = ctx
        # pylint: disable=protected-access
        ctx._ctx.use_certificate(self._cert)
        ctx._ctx.use_privatekey(self._key)
        # pylint: enable=protected-access
        return super().init_poolmanager(*args, **kwargs)


class SterlingOMSClient:
    """A remote client for Sterling Order Management System."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        client_cert: str,
        client_key: str,
    ):
        """
        Args:
            base_url: The base URL for Sterling OMS API.
            username: The username for basic auth.
            password: The password for basic auth.
            client_cert: Client ID for Sterling OMS API.
            client_key: Client secret for Sterling OMS API.
        """
        # setup adapter
        self.adapter: Optional[requests.adapters.BaseAdapter] = ClientSideCertificateHTTPAdapter(
            cert_pem_str=client_cert, key_pem_str=client_key
        )

        assert self.adapter is not None, "Failed to create the adapter"

        self.session = requests.Session()
        self.session.mount("https://", self.adapter)

        # Obtain JWT Token
        self.base_url = base_url

        self.auth = HTTPBasicAuth(username, password)

        self.jwt_token = self._get_jwt_token()

        assert self.jwt_token, "Failed to fetch JWT token for client"

        self.headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get_jwt_token(self) -> str:
        """retrieves the JWT token for authentication."""
        login_url = f"{self.base_url}/invoke/login"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload = {"LoginID": self.auth.username, "Password": self.auth.password}
        try:
            response = self.session.post(
                login_url,
                auth=self.auth,
                headers=headers,
                verify=certifi.where(),
                json=payload,
            )
        except RequestException:
            return ""

        self.user_token = response.json().get("UserToken")

        params = {
            "_token": self.user_token,
            "_loginid": self.auth.username,
        }

        jwt_url = f"{self.base_url}/jwt"
        try:
            jwt = self.session.get(jwt_url, params=params)
        except RequestException:
            return ""

        assert jwt.status_code == 200

        return jwt.text

    def delete_request(
        self,
        resource_name: str,
        params: Optional[dict[str, Any]] = None,
    ) -> Union[int, Dict[str, Any]]:
        """
        Executes a DELETE request against Sterling OMS API.

        Args:
            resource_name: The specific resource to make the request against.
            params: Query parameters for the REST API.

        Returns:
            HTTP status code on success, or an error dictionary on failure.
        """
        if params is None:
            params = {}

        try:
            response = self.session.delete(
                url=f"{self.base_url}/{resource_name}",
                headers=self.headers,
                params=json.dumps(params),
                auth=self.auth,
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
        payload: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a PATCH request against Sterling OMS API.

        Args:
            resource_name: The specific resource to make the request against.
            payload: The request payload.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the Sterling OMS REST API.
        """
        if params is None:
            params = {}
        if payload is None:
            payload = {}

        try:
            response = self.session.patch(
                url=f"{self.base_url}/{resource_name}",
                headers=self.headers,
                params=params,
                json=payload,
                auth=self.auth,
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
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a POST request against Sterling OMS API.

        Args:
            resource_name: The specific resource to make the request against.
            params: Query parameters for the REST API.
            payload: The request payload.

        Returns:
            The JSON response from the Sterling OMS REST API.
        """
        if params is None:
            params = {}

        try:
            response = self.session.post(
                url=f"{self.base_url}/{resource_name}",
                headers=self.headers,
                params=params,
                data=json.dumps(payload),
                auth=self.auth,
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
        params: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a GET request against Sterling OMS API.

        Args:
            resource_name: The specific resource to make the request against.
            params: Query parameters for the REST API.

        Returns:
            The JSON list response from the Sterling OMS REST API.
        """
        if params is None:
            params = {}

        try:
            response = self.session.get(
                url=f"{self.base_url}/{resource_name}",
                headers=self.headers,
                params=params,
                auth=self.auth,
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


def get_sterling_oms_client() -> SterlingOMSClient:
    """
    Get the Sterling OMS client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the Sterling OMS client.
    """
    credentials = get_tool_credentials(Systems.STERLING_OMS)
    sterling_oms_client = SterlingOMSClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        username=credentials[CredentialKeys.USERNAME],
        password=credentials[CredentialKeys.PASSWORD],
        client_cert=credentials[CredentialKeys.CLIENT_CERT],
        client_key=credentials[CredentialKeys.CLIENT_KEY],
    )
    return sterling_oms_client
