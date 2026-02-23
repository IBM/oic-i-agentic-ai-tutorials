from http import HTTPMethod, HTTPStatus
from typing import Any, Type

import requests
from xsdata.formats.dataclass.context import XmlContext
from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

from agent_ready_tools.clients.auth_manager import WorkdayAuthManager
from agent_ready_tools.clients.clients_enums import AccessLevel
from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_soap_error_details,
    handling_exceptions,
)
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems

RETRY_COUNT = 2


class WorkdaySOAPClient:
    """A remote client for Workday SOAP endpoints."""

    def __init__(
        self,
        base_url: str,
        token_url: str,
        tenant_name: str,
        client_id: str,
        client_secret: str,
        initial_bearer_token: str,
        initial_refresh_token: str,
        soapenv_attr: str = "http://schemas.xmlsoap.org/soap/envelope/",
        api_version: str = "v43.2",
    ):
        """
        Args:
            base_url: The base URL for the Workday API.
            token_url: The URL for authentication tokens for the Workday API.
            tenant_name: The name of the tenant.
            client_id: The client ID to authenticate with.
            client_secret: The client secret to authenticate with.
            initial_bearer_token: The initial bearer token from wxo-domains credentials file.
            initial_refresh_token: The initial refresh token from wxo-domains credentials file.
            soapenv_attr: The value for the 'soapenv' XML tag attribute to include in requests.
            api_version: The version of the workday SOAP API being used.
        """
        self.base_url = base_url
        self.tenant_name = tenant_name
        self.headers = {
            "Content-Type": "text/xml;charset=UTF-8",
        }
        self.auth_manager = WorkdayAuthManager(
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
            initial_bearer_token=initial_bearer_token,
            initial_refresh_token=initial_refresh_token,
            # TODO: make this an init param if a SOAP endpoint ever needs manager creds
            access_level=AccessLevel.EMPLOYEE,
        )

        self.soapenv_attr = soapenv_attr
        self.api_version = api_version
        self.xml_namespace_map = {"bsvc": "urn:com.workday/bsvc"}

        serializer_config = SerializerConfig(
            pretty_print=True,
            xml_declaration=True,
            indent="    ",
        )
        self.serializer = XmlSerializer(config=serializer_config)
        self.parser = XmlParser(context=XmlContext())

    def _request_with_reauth(
        self,
        method: str,
        url: str,
        data: str,
    ) -> requests.Response | ErrorDetails:
        """Makes a <method> request to the given URL with the given data, retrying on token
        expiry."""
        for trial in range(RETRY_COUNT):  # 1 retry
            self.headers["Authorization"] = f"Bearer {self.auth_manager.get_bearer_token()}"
            response: requests.Response | None = None
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    data=data,
                )
                response.raise_for_status()
                break
            except Exception as e:  # pylint: disable=broad-except
                if (
                    response is not None
                    and response.status_code == HTTPStatus.UNAUTHORIZED
                    and trial < RETRY_COUNT - 1
                ):
                    self.auth_manager.refresh_bearer_token()
                else:
                    if response is not None:
                        return extract_soap_error_details(response=response)
                    else:
                        return handling_exceptions(exception=e, url=url)
        assert response is not None  # mypy
        return response

    def post_request(
        self,
        service_path: str,
        service_name: str,
        payload: Any,
        output_type: Type[Any],
    ) -> Any:
        """
        Sends a POST request to a Workday SOAP endpoint.

        Args:
            service_path: The path for the SOAP client service.
            service_name: The name of the Workday SOAP service (e.g., Human_Resources).
            payload: The dataclass representing the request XML input.
            output_type: The dataclass type for the request XML output.

        Returns:
            The dataclass representing the request XML output or the API request error details if.
        """
        serialized_request = self.serializer.render(payload, ns_map=self.xml_namespace_map)
        url = f"{self.base_url}/{service_path}/{self.tenant_name}/{service_name}/{self.api_version}"

        response = self._request_with_reauth(
            method=HTTPMethod.POST,
            url=url,
            data=serialized_request,
        )
        if isinstance(response, ErrorDetails):
            return response
        output = self.parser.from_bytes(response.content, output_type)
        return output


def get_workday_soap_client(
    access_level: AccessLevel = AccessLevel.EMPLOYEE,
) -> WorkdaySOAPClient | ErrorDetails:
    """
    Get the workday soap client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Args:
        access_level: It defines the persona of the logged-in user. By default, the value is
            EMPLOYEE.

    Returns:
        A new instance of the Workday SOAP client or the error details object if an error occurs while initalizing the client and its credentials.
    """
    try:
        credentials = get_tool_credentials(system=Systems.WORKDAY, sub_category=access_level)
        workday_soap_client = WorkdaySOAPClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            token_url=credentials[CredentialKeys.TOKEN_URL],
            client_id=credentials[CredentialKeys.CLIENT_ID],
            client_secret=credentials[CredentialKeys.CLIENT_SECRET],
            tenant_name=credentials[CredentialKeys.TENANT_NAME],
            initial_bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
            initial_refresh_token=credentials[CredentialKeys.REFRESH_TOKEN],
        )
    except (
        AssertionError,
        ValueError,
        KeyError,
        AttributeError,
        requests.exceptions.RequestException,
    ) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Workday client initialization:{str(e)}",
            details=f"Caught error during Workday client initialization:{str(e)}",
            recommendation=None,
        )
    return workday_soap_client
