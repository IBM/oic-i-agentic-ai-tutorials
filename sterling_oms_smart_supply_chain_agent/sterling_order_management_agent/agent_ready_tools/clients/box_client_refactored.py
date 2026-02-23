from enum import StrEnum
import http
from typing import Any, Optional

import requests

from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    extract_error_details,
    handling_exceptions,
    no_data_in_get_request,
)
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class BoxAPIType(StrEnum):
    """Encapsulates API Prefixes for Box."""

    API = "api"
    UPLOAD = "upload"


class BoxClient:
    """A remote client for Box API."""

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
    ):
        """
        Args:
            base_url: The base URL for the Box API.
            bearer_token: The token used for authentication returned by WxO Connection-Manager.

        Returns:
            None
        """
        self._box_domain = "box.com"
        self.box_base_url = base_url
        self.headers = {"Authorization": f"Bearer {bearer_token}", "Accept": "application/json"}

    def get_request(
        self, entity: str, params: Optional[dict[str, Any]] = None, content: Optional[bool] = False
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a GET request against a Box API.

        Args:
            entity (str): The entity to retrieve from the Box API.
            params (dict[str, Any], optional): The parameters to include in the GET request. Defaults to None.
            content (bool): This is optional parameter to retrieve the file content as text. Defaults to False.

        Returns:
            dict[str, Any]: The JSON response from the Box API or the API request error details if an error occurs during the API call.
        """
        # entries content
        url = self.__build_url(entity)
        response: requests.Response | None = None
        try:
            response = requests.get(
                url=url,
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            if content:
                return {"content": response.text}
            json_response = response.json()
            if len(json_response.get("entries", [])) == 0:
                return no_data_in_get_request(response=response)
            return json_response
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def post_request(
        self,
        entity: str,
        data: Optional[dict[str, Any]] = None,
        files: Optional[dict[str, Any]] = None,
        api_type: BoxAPIType = BoxAPIType.API,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a POST request against a Box API.

        Args:
            entity (str): The entity path for the request (e.g., "files/content").
            data (dict[str, Any], optional): The data to include in the POST request. Defaults to None.
            files (dict[str, Any], optional): The files to upload. Defaults to None.
            api_type (str, optional): The API type to use ("api" or "upload"). Defaults to "api".

        Returns:
            dict[str, Any]: The JSON response from the Box API or the API request error details if an error occurs during the API call.
        """
        url = self.__build_url(entity, api_type)
        response: requests.Response | None = None
        try:
            response = requests.post(
                url=url,
                headers=self.headers,
                json=data,
                files=files,
            )
            if response.status_code != http.HTTPStatus.CONFLICT.value:
                response.raise_for_status()
            result = response.json()
            result["status_code"] = response.status_code
            return result
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def put_request(
        self,
        entity: str,
        data: Optional[dict[str, Any]] = None,
        api_type: BoxAPIType = BoxAPIType.API,
    ) -> dict[str, Any] | ErrorDetails:
        """
        Executes a PUT request against a Box API.

        Args:
            entity (str): The entity path for the request (e.g., "folders/4353455").
            data (dict[str, Any], optional): The data to include in the PUT request. Defaults to None.
            api_type (str, optional): The API type to use ("api" or "upload"). Defaults to "api".

        Returns:
            dict[str, Any]: The JSON response from the Box API or the API request error details if an error occurs during the API call.
        """
        url = self.__build_url(entity, api_type)
        response: requests.Response | None = None
        try:
            response = requests.put(
                url=url,
                headers=self.headers,
                json=data,
            )
            response.raise_for_status()
            json_response = response.json()
            return json_response
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)

    def delete_request(
        self,
        entity: str,
        params: Optional[dict[str, Any]] = None,
        api_type: BoxAPIType = BoxAPIType.API,
    ) -> int | ErrorDetails:
        """
        Executes a DELETE request against a Box API.

        Args:
            entity (str): The entity path for the request (e.g., "folders/4353455").
            params (dict[str, Any], optional): The parameters to include in the DELETE request. Defaults to None.
            api_type (str, optional): The API type to use ("api" or "upload"). Defaults to "api".

        Returns:
            int: The status code of the response if there is no content, otherwise the JSON response from the Box API  or the API request error details if an error occurs during the API call.
        """
        url = self.__build_url(entity, api_type)
        response: requests.Response | None = None
        try:
            response = requests.delete(
                url=url,
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
        except Exception as e:  # pylint: disable=broad-except
            if response is not None:
                return extract_error_details(response=response)
            else:
                return handling_exceptions(exception=e, url=url)
        if response.content:
            return response.json()
        return response.status_code

    def __build_url(self, entity: str, api_type: BoxAPIType = BoxAPIType.API) -> str:
        """
        Build the appropriate URL for Box API requests.

        Args:
            entity (str): The entity path for the request.
            api_type (str): The API type to use ("api" or "upload"). Defaults to "api".

        Returns:
            str: The fully constructed URL.
        """
        # https://upload.{self.box_base_url}/api/2.0/{entity} or
        # https://api.{self.box_base_url}/2.0/{entity}
        prefixed_url = self.box_base_url.replace(
            self._box_domain, f"{api_type}.{self._box_domain}", 1
        )
        if api_type == BoxAPIType.UPLOAD:
            prefixed_url = f"{prefixed_url}/api"
        return f"{prefixed_url}/2.0/{entity}"


def get_box_client() -> BoxClient | ErrorDetails:
    """
    Get the box client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the Box client or the error details if an error occurs during creating new instance of the Google client.
    """
    try:
        credentials = get_tool_credentials(Systems.BOX)
        box_client = BoxClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            bearer_token=credentials[CredentialKeys.BEARER_TOKEN],
        )
    except (AssertionError, ValueError, requests.exceptions.RequestException) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Box client initialization:{str(e)}",
            details=f"Caught error during Box client initialization:{str(e)}",
            recommendation=None,
        )
    return box_client
