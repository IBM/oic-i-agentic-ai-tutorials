import requests
from requests.auth import HTTPBasicAuth
from xsdata.formats.dataclass.context import XmlContext
from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

from agent_ready_tools.apis.oracle_hcm_soap_services.learningbireport import api as learn_api
from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    handling_exceptions,
)
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class OracleSOAPClient:
    """A remote client for Oracle SOAP endpoints."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        soapenv_attr: str = "http://www.w3.org/2003/05/soap-envelope",
    ):
        """
        Args:
            base_url: The base URL for the Oracle HCM API.
            username: The username to use for authentication against the Oracle HCM API.
            password: The password to use for authentication against the Oracle HCM API.
            soapenv_attr: The value for the 'soapenv' XML tag attribute to include in requests.
        """
        self.base_url = base_url
        self.auth = HTTPBasicAuth(username, password)
        self.headers = {
            "Content-Type": "application/soap+xml;charset=UTF-8",
        }
        self.soapenv_attr = soapenv_attr
        self.xml_namespace_map = {"pub": "http://xmlns.oracle.com/oxp/service/PublicReportService"}

        serializer_config = SerializerConfig(
            pretty_print=True,
            xml_declaration=True,
            indent="    ",
        )
        self.serializer = XmlSerializer(config=serializer_config)
        self.parser = XmlParser(context=XmlContext())

    def oracle_get_courses(
        self, payload: learn_api.ExternalReportWssserviceRunReportInput
    ) -> learn_api.ExternalReportWssserviceRunReportOutput | bytes | ErrorDetails:
        """
        Gets course details from Oracle HCM.

        Args:
            payload: The dataclass representing the ExternalReportWssserviceRunReportInput request
                XML input.

        Returns:
            The dataclass representing the ExternalReportWssserviceRunReportOutput request XML
            output or the API request error details if an error occurs during the API call.
        """
        serialized_request = self.serializer.render(payload, ns_map=self.xml_namespace_map)
        headers = {"Content-Type": "application/soap+xml"}
        url = f"{self.base_url}/xmlpserver/services/ExternalReportWSSService"
        response: requests.Response | None = None
        try:
            response = requests.post(
                url=url,
                data=serialized_request,
                auth=self.auth,
                headers=headers,
            )
            response.raise_for_status()
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)
        output = self.parser.from_bytes(
            response.content, learn_api.ExternalReportWssserviceRunReportOutput
        )
        return output

    def oracle_get_specializations(
        self, payload: learn_api.ExternalReportWssserviceRunReportInput
    ) -> learn_api.ExternalReportWssserviceRunReportOutput | ErrorDetails:
        """
        Gets specialization details from Oracle HCM.

        Args:
            payload: The dataclass representing the ExternalReportWssserviceRunReportInput request
                XML input.

        Returns:
            The dataclass representing the ExternalReportWssserviceRunReportOutput request XML
            output or the API request error details if an error occurs during the API call.
        """
        serialized_request = self.serializer.render(payload, ns_map=self.xml_namespace_map)
        headers = {"Content-Type": "application/soap+xml"}
        url = f"{self.base_url}/xmlpserver/services/ExternalReportWSSService"
        response: requests.Response | None = None
        try:
            response = requests.post(
                url=url,
                data=serialized_request,
                auth=self.auth,
                headers=headers,
            )
            response.raise_for_status()
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)
        output = self.parser.from_bytes(
            response.content, learn_api.ExternalReportWssserviceRunReportOutput
        )
        return output

    def oracle_get_course_offerings(
        self, payload: learn_api.ExternalReportWssserviceRunReportInput
    ) -> learn_api.ExternalReportWssserviceRunReportOutput | ErrorDetails:
        """
        Gets offering details from Oracle HCM.

        Args:
            payload: The dataclass representing the ExternalReportWssserviceRunReportInput request
                XML input.

        Returns:
            The dataclass representing the ExternalReportWssserviceRunReportOutput request XML
            output or the API request error details if an error occurs during the API call.
        """
        serialized_request = self.serializer.render(payload, ns_map=self.xml_namespace_map)
        headers = {"Content-Type": "application/soap+xml"}
        url = f"{self.base_url}/xmlpserver/services/ExternalReportWSSService"
        response: requests.Response | None = None
        try:
            response = requests.post(
                url=url,
                data=serialized_request,
                auth=self.auth,
                headers=headers,
            )
            response.raise_for_status()
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)
        output = self.parser.from_bytes(
            response.content, learn_api.ExternalReportWssserviceRunReportOutput
        )
        return output


def get_oracle_soap_client() -> OracleSOAPClient | ErrorDetails:
    """
    Get the oracle soap client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the Oracle SOAP client or the error details object if an error occurs while initializing the client and its credentials.
    """
    try:
        credentials = get_tool_credentials(system=Systems.ORACLE_HCM)
        oracle_soap_client = OracleSOAPClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            username=credentials[CredentialKeys.USERNAME],
            password=credentials[CredentialKeys.PASSWORD],
        )
    except (AssertionError, ValueError, KeyError, requests.exceptions.RequestException) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Oracle SOAP client initialization:{str(e)}",
            details=f"Caught error during Oracle SOAP client initialization:{str(e)}",
            recommendation=None,
        )
    return oracle_soap_client
