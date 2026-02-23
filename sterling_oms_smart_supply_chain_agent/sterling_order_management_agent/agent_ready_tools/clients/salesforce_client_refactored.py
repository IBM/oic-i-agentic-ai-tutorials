from typing import Any, Optional

import requests
from simple_salesforce import Salesforce  # type: ignore[attr-defined]

from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    handling_exceptions,
    no_data_in_get_request,
)
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class SalesforceClient:
    """A remote client for Salesforce."""

    def __init__(self, base_url: str, token: str):
        """
        Args:
            base_url: The base URL for the Salesforce API.
            token: The access token to authenticate with.
        """
        self.__base_url = base_url
        self.__headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        self.__token = token
        self.salesforce_object = Salesforce(instance_url=self.__base_url, session_id=self.__token)

    def post_request(
        self,
        api_version: str,
        resource_name: str,
        payload: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a POST request against Salesforce API.

        Args:
            api_version: Specific api_version.
            resource_name: The specific resource to make the request against.
            payload: The request payload.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the Salesforce REST API or the API request error details if an error occurs during the API call.
        """

        headers = {
            "Authorization": f"Bearer {self.__token}",
            "Accept": self.__headers["Accept"],
        }
        url = f"{self.__base_url}/services/data/{api_version}/{resource_name}"
        response: requests.Response | None = None
        try:
            response = requests.post(
                url=url,
                headers=headers,
                params=params,
                json=payload,
            )
            response.raise_for_status()
            json_response = response.json()
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)
        return json_response

    def patch_request(
        self,
        api_version: str,
        resource_name: str,
        payload: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> int | ErrorDetails:
        """
        Executes a PATCH request against Salesforce API.

        Args:
            api_version: Specific api_version.
            resource_name: The specific resource to make the request against.
            payload: The request payload.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the Salesforce REST API or the API request error details if an error occurs during the API call.
        """

        headers = {
            "Authorization": f"Bearer {self.__token}",
            "Accept": self.__headers["Accept"],
        }

        url = f"{self.__base_url}/services/data/{api_version}/{resource_name}"
        response: requests.Response | None = None
        try:
            response = requests.patch(
                url=url,
                headers=headers,
                params=params,
                json=payload,
            )
            response.raise_for_status()
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)
        return response.status_code

    def delete_request(
        self,
        api_version: str,
        resource_name: str,
        payload: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> int | ErrorDetails:
        """
        Executes a DELETE request against Salesforce API.

        Args:
            api_version: Specific api_version.
            resource_name: The specific resource to make the request against.
            payload: The request payload.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the Salesforce REST API or the API request error details if an error occurs during the API call.
        """

        headers = {
            "Authorization": f"Bearer {self.__token}",
            "Accept": self.__headers["Accept"],
        }

        url = f"{self.__base_url}/services/data/{api_version}/{resource_name}"
        response: requests.Response | None = None
        try:
            response = requests.delete(
                url=url,
                headers=headers,
                params=params,
                json=payload,
            )
            response.raise_for_status()
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        return response.status_code

    def get_request(
        self,
        api_version: str,
        resource_name: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a GET request against Salesforce API.

        Args:
            api_version: Specific api_version.
            resource_name: The specific resource to make the request against.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the Salesforce REST API or the API request error details if an error occurs during the API call.
        """

        headers = {
            "Authorization": f"Bearer {self.__token}",
            "Accept": self.__headers["Accept"],
        }

        url = f"{self.__base_url}/services/data/{api_version}/{resource_name}"
        response: requests.Response | None = None
        try:
            response = requests.get(
                url=f"{self.__base_url}/services/data/{api_version}/{resource_name}",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            json_response = response.json()
            if not json_response.get("values", None):
                return no_data_in_get_request(response=response)
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        return json_response

    def get_picklist_options(
        self, object_api_name: str, field_api_name: str, record_type_id: Optional[str] = None
    ) -> dict[str, Any] | ErrorDetails:
        """
        Gets the picklist options for the specified fields.

        Args:
            object_api_name: The API name of a supported object in Salesforce.
            field_api_name: The API name of the picklist field on the object in Salesforce.
            record_type_id: The record type id of the object API in Salesforce.

        Returns:
            A dictionary representing the picklist options for the specified fields or the API request error details if an error occurs during the API call.
        """

        headers = {
            "Authorization": f"Bearer {self.__token}",
            "Accept": self.__headers["Accept"],
        }

        if not record_type_id:
            record_type_id = (
                requests.get(
                    url=f"{self.__base_url}/services/data/v63.0/ui-api/object-info/{object_api_name}",
                    headers=headers,
                )
                .json()
                .get("defaultRecordTypeId")
            )
        response: requests.Response | None = None
        try:
            url = f"{self.__base_url}/services/data/v63.0/ui-api/object-info/{object_api_name}/picklist-values/{record_type_id}/{field_api_name}"
            response = requests.get(
                url=url,
                headers=headers,
            )
            response.raise_for_status()
            json_response = response.json()
            if not json_response.get("values", None):
                return no_data_in_get_request(response=response)
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

        return json_response


def get_salesforce_client() -> SalesforceClient | ErrorDetails:
    """
    Get the salesforce client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of Salesforce or the API request error details if an error occurs during the API call.
    """
    try:
        credentials = get_tool_credentials(Systems.SALESFORCE)
        salesforce_client = SalesforceClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            token=credentials[CredentialKeys.BEARER_TOKEN],
        )
    except (AssertionError, ValueError, requests.exceptions.RequestException) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Salesforce client initialization:{str(e)}",
            details=f"Caught error during Salesforce client initialization:{str(e)}",
            recommendation=None,
        )
    return salesforce_client
