from typing import Any, Optional

import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException

from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems


class SAPS4HanaClient:
    """A remote client for SAP S4 Hana."""

    def __init__(self, base_url: str, username: str, password: str):
        """
        Args:
            base_url: The base URL for the SAP S4 Hana API.
            username: The username to use for authentication against the SAP S4 Hana API.
            password: The password to use for authentication against the SAP S4 Hana API.
        """

        self.base_url = base_url
        self.auth = HTTPBasicAuth(username, password)
        assert self.auth

    def get_request(
        self,
        entity: str,
        params: Optional[dict[str, Any]] = None,
        filter_expr: Optional[str] = None,
        select_expr: Optional[str] = None,
        expand_expr: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Executes a GET request against the provided OData entity.

        Args:
            entity: The OData entity to query.
            params: Query parameters for the REST API.
            filter_expr: An optional OData filter expression to restrict the results.
            select_expr: An optional OData select expression specifying which fields to include in
                the response.
            expand_expr: An optional OData expand expression specifying which fields to expand.

        Returns:
            The JSON response from the SAP S4 Hana API.
        """

        url = f"{self.base_url}/{entity}"

        if params is None:
            params = {"$format": "json"}
        elif "$format" not in params:
            params["$format"] = "json"
        if filter_expr is not None:
            params["$filter"] = filter_expr
        if select_expr is not None:
            params["$select"] = select_expr
        if expand_expr is not None:
            params["$expand"] = expand_expr

        headers = {"x-csrf-token": "Fetch"}

        response = None
        try:
            response = requests.get(url=url, params=params, auth=self.auth, headers=headers)
            response.raise_for_status()
            return {
                "response": response.json(),
                "csrf_token": response.headers.get("x-csrf-token", ""),
                "cookies": response.cookies,
            }
        except RequestException:
            if response is not None:
                try:
                    error_json = response.json()  # if JSON response
                except ValueError:
                    # handle the case where response content is not JSON
                    error_json = {
                        "error": {
                            "message": {
                                "value": "Non-JSON response received",
                                "status_code": getattr(response, "status_code", "Unknown"),
                            },
                        }
                    }
            else:
                # connection error, timeout, etc.
                error_json = {
                    "error": {
                        "message": {
                            "value": "No response received (request failed before getting a response)"
                        },
                    }
                }

            return error_json

    def post_request(
        self,
        entity: str,
        payload: dict[str, Any],
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Executes a POST request against the provided OData entity.

        Args:
            entity: The OData entity to query.
            payload: A dictionary containing the input payload.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the SAP S4 Hana API.
        """
        url = f"{self.base_url}/{entity}"

        # Using utility function to get csrf_token and cookies for headers.
        csrf_response = self.get_csrf_token()

        if "error" in csrf_response:
            error_json = {
                "error": {
                    "message": {"value": "Invalid credentials"},
                }
            }
            return error_json

        headers = {
            "x-csrf-token": csrf_response["csrf_token"],
            "Content-Type": "application/json",
            "Cookie": csrf_response["cookies"],
            "Accept": "application/json",
        }

        try:
            response = requests.post(
                url=url, json=payload, headers=headers, auth=self.auth, params=params
            )
            response.raise_for_status()
            return response.json()

        except RequestException:
            if response is not None:
                try:
                    error_json = response.json()  # if JSON response
                except ValueError:
                    # handle the case where response content is not JSON
                    error_json = {
                        "error": {
                            "message": {
                                "value": "Non-JSON response received",
                                "status_code": getattr(response, "status_code", "Unknown"),
                            },
                        }
                    }
            else:
                # connection error, timeout, etc.
                error_json = {
                    "error": {
                        "message": {
                            "value": "No response received (request failed before getting a response)"
                        },
                    }
                }

            return error_json

    def patch_request(
        self, entity: str, payload: dict[str, Any], params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Executes a PATCH request against the provided OData entity.

        Args:
            entity: The OData entity to query.
            payload: A dictionary containing the input payload.
            params: Query parameters for the REST API.

        Returns:
            The JSON response from the SAP S4 Hana API.
        """
        url = f"{self.base_url}/{entity}"

        # Using utility function to get csrf_token and cookies for headers.
        csrf_response = self.get_csrf_token()

        if "error" in csrf_response:
            error_json = {
                "error": {
                    "message": {"value": "Invalid credentials"},
                }
            }
            return error_json

        headers = {
            "x-csrf-token": csrf_response["csrf_token"],
            "Content-Type": "application/json",
            "Cookie": csrf_response["cookies"],
            "Accept": "application/json",
        }

        try:
            response = requests.patch(
                url=url, json=payload, headers=headers, auth=self.auth, params=params
            )
            response.raise_for_status()
            return {"http_code": response.status_code}

        except RequestException:
            if response is not None:
                try:
                    error_json = response.json()  # if JSON response
                except ValueError:
                    # handle the case where response content is not JSON
                    error_json = {
                        "error": {
                            "message": {
                                "value": "Non-JSON response received",
                                "status_code": getattr(response, "status_code", "Unknown"),
                            },
                        }
                    }
            else:
                # connection error, timeout, etc.
                error_json = {
                    "error": {
                        "message": {
                            "value": "No response received (request failed before getting a response)"
                        },
                    }
                }

            return error_json

    def delete_request(
        self,
        entity: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Executes a DELETE request against the provided OData entity.

        Args:
            entity: The OData entity to query.
            payload: A dictionary containing the input payload.

        Returns:
            The JSON response from the SAP S4 Hana API.
        """

        url = f"{self.base_url}/{entity}"

        # Using utility function to get csrf_token and cookies for headers.
        csrf_response = self.get_csrf_token()

        if "error" in csrf_response:
            error_json = {
                "error": {
                    "message": {"value": "Invalid credentials"},
                }
            }
            return error_json

        headers = {
            "x-csrf-token": csrf_response["csrf_token"],
            "Content-Type": "application/json",
            "Cookie": csrf_response["cookies"],
        }

        try:
            response = requests.delete(url=url, json=payload, headers=headers, auth=self.auth)
            response.raise_for_status()
            return response.json()

        except RequestException:
            if response is not None:
                try:
                    error_json = response.json()  # if JSON response
                except ValueError:
                    # handle the case where response content is not JSON
                    error_json = {
                        "error": {
                            "message": {
                                "value": "Non-JSON response received",
                                "status_code": getattr(response, "status_code", "Unknown"),
                            },
                        }
                    }
            else:
                # connection error, timeout, etc.
                error_json = {
                    "error": {
                        "message": {
                            "value": "No response received (request failed before getting a response)"
                        },
                    }
                }

            return error_json

    def get_csrf_token(self) -> dict[str, Any]:
        """
        A function to obtain a CSRF token and cookies from a GET request, which can then be utilized
        in POST, PATCH, or DELETE requests.

        Returns:
            The csrf_token and cookies from a get request
        """
        params = {"$top": "1"}
        response = self.get_request(
            entity="API_BUSINESS_PARTNER/A_BusinessPartner",
            params=params,
            select_expr="BusinessPartner,Customer,Supplier",
        )

        if "cookies" not in response:
            error_json = {
                "error": {
                    "message": {
                        "value": "Non-JSON response received",
                        "status_code": getattr(response, "status_code", "Unknown"),
                    },
                }
            }
            return error_json

        cookies = response["cookies"]
        sap_user_context = cookies.get("sap-usercontext")
        sap_session_id = cookies.get("SAP_SESSIONID_S7B_500")
        cookies = f"SAP_SESSIONID_S7B_500={sap_session_id}; sap-usercontext={sap_user_context}"

        return {"csrf_token": response["csrf_token"], "cookies": cookies}


def get_sap_s4_hana_client() -> SAPS4HanaClient:
    """
    Get the sap s4 hana client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the SAP S4 Hana client.
    """
    credentials = get_tool_credentials(Systems.SAP_S4_HANA)

    sap_s4_hana_client = SAPS4HanaClient(
        base_url=credentials[CredentialKeys.BASE_URL],
        username=credentials[CredentialKeys.USERNAME],
        password=credentials[CredentialKeys.PASSWORD],
    )
    return sap_s4_hana_client
