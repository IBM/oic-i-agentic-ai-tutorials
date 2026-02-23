# Standard library imports
from http import HTTPMethod, HTTPStatus
import logging
from typing import Any, Dict, Optional

# Third-party library imports
import requests
from requests.auth import HTTPBasicAuth

from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems

logger = logging.getLogger(__name__)


class IBMPlanningAnalyticsClient:
    """A remote client for IBM PA."""

    REST_FRAMEWORK_VERSION = "v1"
    PA_MODEL_DB = "tm1"

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        tenant_id: str,
        model_name: str,
        version: str = REST_FRAMEWORK_VERSION,
    ):
        """
        Args:
            base_url: The base URL for the IBM PA API.
            username: The username to use for authentication against the IBM PA API.
            password: The password to use for authentication against the IBM PA API.
            tenant_id: The tenant id of the IBM PA instance.
            model_name: The database name of PA instance.
            version: The version of IBM PA API.
        """
        self.base_url = base_url
        self.auth = HTTPBasicAuth(username, password)
        self.tenant_id = tenant_id
        self.model_name = model_name
        self.version = version
        self._fetch_session_token()

    def _fetch_session_token(self) -> None:
        """
        Obtains a new authentication token that is return in the response as the cookie value for
        'paSession' key.

        All subsequent requests to IBM Planning Analytics instance is using this key/value pair in
        the request cookies. We achieve that by reusing session object which takes care of the
        cookies.
        """
        url = f"{self.base_url}/api/{self.tenant_id}/v0/rolemgmt/{self.version}/users/me"
        headers = {"Accept": "application/json"}
        self.session = requests.Session()
        auth_response = self.session.get(url=url, auth=self.auth, headers=headers)
        auth_response.raise_for_status()

    def _request_with_reauth(
        self,
        method: str,
        url: str,
        retries: int = 2,
        headers: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """Makes a <method> request to the given URL with the given params and payload, retrying on
        token expiry."""

        for _ in range(retries):  # 1 retry
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
                json=payload,
            )
            if response.status_code == HTTPStatus.UNAUTHORIZED:
                self._fetch_session_token()
            else:
                break
        return response

    def get_request(
        self,
        entity: str,
        entity_id: Optional[str] = None,
        embedded_entity: Optional[str] = None,
        action: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        path: Optional[str] = "api",
        params: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """
        Executes a GET request against the provided entity.

        Args:
            entity: The entity to query.
            entity_id: An optional entity_id (identifier/name) to query.
            embedded_entity: An optional entity that is related to the base entity.
            action: The optional action to call on the specified entity.
            headers: An optional headers which are required for API request.
            path: An optional path value that is used to called list of values apis.
            params: Query parameters for the REST API.

        Returns:
            The Response object from the IBM PA API call.
        """
        url = f"{self.base_url}/{self.PA_MODEL_DB}/{self.model_name}/{path}/{self.version}/{entity}"
        if entity_id:
            url = f"{url}('{entity_id}')"
            if embedded_entity:
                url = f"{url}/{embedded_entity}"
            if action:
                url = f"{url}/{self.PA_MODEL_DB}.{action}"

        if headers is None:
            headers = {}

        response: requests.Response = self._request_with_reauth(
            method=HTTPMethod.GET, url=url, params=params, headers=headers
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.info(f"The request failed with error: {e}")
        return response

    def post_request(
        self,
        entity: str,
        payload: dict[str, Any],
        path: Optional[str] = "api",
        entity_id: Optional[str] = None,
        action: Optional[str] = None,
        embedded_entity: Optional[str] = None,
        params: Optional[dict[str, str]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """
        Executes a generic upsert request against the IBM PA API.

        Args:
            entity: The base entity (resource) in IBM PA to work on (for example, Cube, Sandbox).
            payload: A dictionary containing the input payload.
            path: An optional path value that is used to called list of values apis.
            entity_id: An optional entity_id (identifier/name) to query.
            action: An optional action to call on the specified entity.
            embedded_entity: An optional entity which is embedded inside the entity.
            params: A dictionary containing the request params (Optional).
            headers: A dictionary containing the request headers (Optional).

        Returns:
            The JSON response from the IBM PA API.
        """
        url = f"{self.base_url}/{self.PA_MODEL_DB}/{self.model_name}/{path}/{self.version}/{entity}"
        if entity_id:
            url = f"{url}('{entity_id}')"
            if embedded_entity:
                url = f"{url}/{embedded_entity}"
            if action:
                url = f"{url}/{self.PA_MODEL_DB}.{action}"

        if headers is None:
            headers = {"REST-Framework-Version": self.REST_FRAMEWORK_VERSION}
        else:
            headers["REST-Framework-Version"] = self.REST_FRAMEWORK_VERSION

        response = self._request_with_reauth(
            method=HTTPMethod.POST,
            url=url,
            payload=payload,
            headers=headers,
            params=params,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            # the ibm_pa error response text is more valuable than 'reason', return if available.
            # response text will contain real reason for failing, such as incorrect zip code format.
            if response.text:
                ibm_pa_error_message = (
                    f"{response.status_code} Server Error: {response.text} for url: {response.url}"
                )
                result: Dict[str, Any] = {}
                result["message"] = ibm_pa_error_message
                result["status_code"] = response.status_code
                return result
            raise e
        if response.status_code != HTTPStatus.NO_CONTENT.value:
            result = response.json()
        else:
            result = {}
        result["status_code"] = response.status_code
        return result

    def update_request(
        self, entity: str, payload: dict[str, Any], entity_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Executes the update request against the provided entity in IBM PA.

        Args:
            entity: The entity to query.
            payload: A dictionary containing the input payload.
            entity_id: An optional entity_id (identifier/name) to query.

        Returns:
            The JSON response from the IBM PA API.
        """

        url = f"{self.base_url}/{self.PA_MODEL_DB}/{self.model_name}/api/{self.version}/{entity}"
        if entity_id:
            url = f"{url}('{entity_id}')"

        headers = {"Content-Type": "application/json"}
        response = self._request_with_reauth(
            method=HTTPMethod.PATCH,
            url=url,
            payload=payload,
            headers=headers,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            # the ibm_pa error response text is more valuable than 'reason', return if available.
            # response text will contain real reason for failing, such as incorrect zip code format.
            if response.text:
                ibm_pa_error_message = (
                    f"{response.status_code} Server Error: {response.text} for url: {response.url}"
                )
                result: Dict[str, Any] = {}
                result["message"] = ibm_pa_error_message
                result["status_code"] = response.status_code
                return result
            raise e

        result = response.json()
        result["status_code"] = response.status_code
        return result

    def delete_request(
        self,
        entity: str,
        entity_id: str,
        path: Optional[str] = "api",
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> int:
        """
        Executes a GET request against the provided entity.

        Args:
            entity: The entity to query.
            entity_id: The entity_id (identifier/name) to query.
            path: An optional path value that is used to called list of values apis.
            params: Query parameters for the REST API.
            headers: An optional headers which are required for API request.

        Returns:
            The JSON response from the IBM PA API.
        """
        url = f"{self.base_url}/{self.PA_MODEL_DB}/{self.model_name}/{path}/{self.version}/{entity}('{entity_id}')"

        if headers is None:
            headers = {}

        response = self._request_with_reauth(
            method=HTTPMethod.DELETE,
            url=url,
            params=params,
            headers=headers,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.info(f"HTTP Error {e}")
        return response.status_code


def get_ibm_pa_client() -> IBMPlanningAnalyticsClient:
    """
    Get the ibm pa client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the IBM PA client.
    """
    credentials = get_tool_credentials(Systems.IBM_PLANNING_ANALYTICS)
    ibm_pa_client = IBMPlanningAnalyticsClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        username=credentials[CredentialKeys.USERNAME],
        password=credentials[CredentialKeys.PASSWORD],
        tenant_id=credentials[CredentialKeys.TENANT_ID],
        model_name=credentials[CredentialKeys.MODEL_NAME],
    )
    return ibm_pa_client
