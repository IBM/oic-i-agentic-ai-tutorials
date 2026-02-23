"""
NOTE: The structure and contents of this file are tied to the import script for importing tools.
Please ensure tools can properly be imported and authenticated into the SDK server after making changes.
"""

from enum import StrEnum
import json
from pathlib import Path
from typing import Dict, Optional

from ibm_watsonx_orchestrate.agent_builder.connections.types import ConnectionType
from ibm_watsonx_orchestrate.run import connections

from agent_ready_tools.utils.env import in_pants_env
from agent_ready_tools.utils.systems import Systems
from agent_ready_tools.utils.tool_credentials import get_expected_credentials


class CredentialKeys(StrEnum):
    """Types of credential keys for different systems."""

    API_KEY = "api_key"
    AUTHORITY = "authority"
    BASE_URL = "base_url"
    BEARER_TOKEN = "bearer_token"
    CLIENT_ID = "client_id"
    CLIENT_SECRET = "client_secret"
    CLIENT_CERT = "client_cert"
    CLIENT_KEY = "client_key"
    PASSWORD = "password"
    REALM = "realm"
    REFRESH_TOKEN = "refresh_token"
    SUBJECT_ID = "subject_id"
    SUBJECT_TYPE = "subject_type"
    TENANT_ID = "tenant_id"
    TENANT_NAME = "tenant_name"
    TOKEN_URL = "token_url"
    USER_ID = "user_id"
    USERNAME = "username"
    BUYER_ANID = "buyer_anid"
    ACCESS_KEY = "access_key"
    SECRET_KEY = "secret_key"
    REGION = "region"
    REQUESTER_PASSWORD = "requester_password"
    DELEGATE_MODE = "delegate_mode"
    SCOPE = "scope"
    INSTANCE_ID = "instance_id"
    MODEL_NAME = "model_name"
    PASSWORD_ADAPTER = "password_adapter"


def _merge_base_and_subcategory(system_creds: Dict, sub_category: Optional[str] = None) -> Dict:
    """
    Returns the base credential values and any values for the specified sub_category.

    Args:
        system_creds: The complete set of credentials for a given system.
        sub_category: The sub-category of creds desired.

    Returns:
        Dict of merged creds.
    """
    if sub_category:
        return {k: v for k, v in system_creds.items() if isinstance(v, str)} | system_creds[
            sub_category
        ]
    else:
        return system_creds


def _get_workday_tenant_from_url(server_url: str, app_id: str) -> str:
    """
    Temp workaround to get tenant_name from server_url for Workday connections to avoid a secondary
    key_value conn.

    Args:
        server_url: The server_url (base_url) for Workday APIs.
        app_id: The app-id of the Workday connection.

    Returns:
        Workday tenant name.
    """
    # TODO: remove workday tenant_name hack once custom keys in connection credentials are supported
    # this hack requires that the 'server_url' field value supplied in the connection/credentials be in the format:
    # 'https://wd2-impl-services1.workday.com/ccx/<tenant_name>'
    server_url_parts = server_url.split("/")
    assert (
        server_url_parts
    ), f"Expected server URL not found in '{Systems.WORKDAY}' connection with app-id '{app_id}'"
    assert (
        len(server_url_parts) > 1
        and server_url_parts[len(server_url_parts) - 1]
        and server_url_parts[len(server_url_parts) - 2] == "ccx"
    ), (
        f"Unexpected server URL format in '{Systems.WORKDAY}' connection with app-id '{app_id}': '{server_url}'. "
        f"Expected format: 'https://wd2-impl-services1.workday.com/ccx/<tenant_name>'"
    )
    return server_url_parts[len(server_url_parts) - 1]


def get_tool_credentials(
    system: Systems,
    sub_category: Optional[str] = None,
) -> Dict:
    """
    Gets tools credentials from SDK server or credentials.json.

    Args:
        system: The system for which to return creds.
        sub_category: A specific sub-category of creds for the given system.

    Returns:
        Dict of creds.
    """
    if system in [Systems.WORKDAY, Systems.ARIBA, Systems.DNB]:
        assert sub_category, f"System {system} must specify a sub-category to obtain credentials."

    # local integration test, return from credentials.json
    if in_pants_env():
        creds_path = Path(__file__).parent / "credentials.json"
        with open(creds_path) as creds:
            system_creds: Dict = json.load(creds).get(system, {})
            return _merge_base_and_subcategory(system_creds, sub_category)

    # in SDK env
    required_connections = get_expected_credentials(system, sub_category)

    assert required_connections, f"No connections defined for system '{system}'"

    if required_connections:
        merged_conn_creds: Dict = {}
        for connection in required_connections:
            if connection.type == ConnectionType.BASIC_AUTH:
                conn = connections.basic_auth(connection.app_id)
                merged_conn_creds[CredentialKeys.USERNAME] = conn.username
                merged_conn_creds[CredentialKeys.PASSWORD] = conn.password
            elif connection.type == ConnectionType.BEARER_TOKEN:
                conn = connections.bearer_token(connection.app_id)
                merged_conn_creds[CredentialKeys.BEARER_TOKEN] = conn.token
            elif connection.type == ConnectionType.API_KEY_AUTH:
                conn = connections.api_key_auth(connection.app_id)
                merged_conn_creds[CredentialKeys.API_KEY] = conn.api_key
            elif connection.type == ConnectionType.OAUTH2_AUTH_CODE:
                conn = connections.oauth2_auth_code(connection.app_id)
                merged_conn_creds[CredentialKeys.BEARER_TOKEN] = conn.access_token
            elif connection.type == ConnectionType.OAUTH2_CLIENT_CREDS:
                conn = connections.oauth2_client_creds(connection.app_id)
                merged_conn_creds[CredentialKeys.BEARER_TOKEN] = conn.access_token
            elif connection.type == ConnectionType.OAUTH_ON_BEHALF_OF_FLOW:
                conn = connections.oauth2_on_behalf_of(connection.app_id)
                merged_conn_creds[CredentialKeys.BEARER_TOKEN] = conn.access_token
            elif connection.type == ConnectionType.OAUTH2_PASSWORD:
                conn = connections.oauth2_password(connection.app_id)
                merged_conn_creds[CredentialKeys.BEARER_TOKEN] = conn.access_token
            elif connection.type == ConnectionType.KEY_VALUE:
                conn = connections.key_value(connection.app_id)
                for key, new_value in conn.items():
                    existing_value = merged_conn_creds.get(key)
                    # orchestrate sometimes returns 'None' instead of actual None
                    if not new_value or new_value == "None":
                        continue
                    if existing_value and existing_value != new_value:
                        raise ValueError(
                            f"For app-id {connection.app_id} there are two same keys '{key}' in credentials with different values: '{new_value}' and '{existing_value}'"
                        )
                    merged_conn_creds[key] = new_value
            else:
                raise ValueError(
                    f"ConnectionType {connection.type} for app-id {connection.app_id} is not supported."
                )
            _none_conn_values = [None, "None", ""]

            if connection.type != ConnectionType.KEY_VALUE and conn.url not in _none_conn_values:
                # give 'base_url' in key_value conn precedence for backward compatibility in SaaS
                if merged_conn_creds.get(CredentialKeys.BASE_URL) in _none_conn_values:
                    merged_conn_creds[CredentialKeys.BASE_URL] = conn.url

            # temp hack to get Workday tenant_name from server_url for oauth2 connection type
            # until platform supports custom keys: https://github.ibm.com/WatsonOrchestrate/wo-tracker/issues/39383
            server_url = merged_conn_creds.get(CredentialKeys.BASE_URL)
            if (
                system == Systems.WORKDAY
                and "workday_oauth2_auth_code" in connection.app_id
                and server_url
            ):
                tenant_name = _get_workday_tenant_from_url(server_url, connection.app_id)
                merged_conn_creds[CredentialKeys.TENANT_NAME] = tenant_name
                # clean server_url for downstream use
                merged_conn_creds[CredentialKeys.BASE_URL] = server_url.removesuffix(
                    "/" + tenant_name
                )
        return merged_conn_creds
    else:
        # see 'create_flattened_module()' in flat_tools.py
        # TODO: remove once all APIs have 'connections' in SDK server
        all_creds: Dict = {"TODO": {}}
        system_creds = all_creds.get(system, {})
        return _merge_base_and_subcategory(system_creds, sub_category)
