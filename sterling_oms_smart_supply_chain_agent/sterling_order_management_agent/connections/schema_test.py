from pathlib import Path
from typing import Any

from connections import schema
from ibm_watsonx_orchestrate.agent_builder.connections.types import (
    APIKeyAuthCredentials,
    BasicAuthCredentials,
    BearerTokenAuthCredentials,
    ConnectionEnvironment,
    KeyValueConnectionCredentials,
    OAuth2AuthCodeCredentials,
    OAuth2ClientCredentials,
    OAuth2PasswordCredentials,
)
from pydantic import ValidationError
import pytest

from agent_ready_tools.utils.tool_credentials import published_app_id


def test_parse_valid_basic_conn_yaml(tmp_path: Path) -> None:
    """
    Tests parsing of a valid 'basic' auth connection config YAML file.

    Args:
        tmp_path: tmp path used to write test YAML files.
    """
    test_data: dict[str, Any] = {
        "spec_version": "v1",
        "kind": "connection",
        "app_id": "valid_basic_auth",
        "environments": {
            "draft": {
                "kind": "basic",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {"username": "test_username", "password": "test_password"},
            },
            "live": {
                "kind": "basic",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {"username": "test_username", "password": "test_password"},
            },
        },
    }

    valid_basic_auth_yaml_template = """
    spec_version: v1
    kind: connection
    app_id: "{app_id}"
    environments:
        draft:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                username: "{username}"
                password: "{password}"
        live:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                username: "{username}"
                password: "{password}"
    """

    temp_file = tmp_path / "test_valid_basic_conn.yaml"
    valid_basic_conn_config_contents = valid_basic_auth_yaml_template.format(
        app_id=test_data["app_id"],
        kind=test_data["environments"]["draft"]["kind"],
        username=test_data["environments"]["draft"]["credentials"]["username"],
        password=test_data["environments"]["draft"]["credentials"]["password"],
        server_url=test_data["environments"]["draft"]["server_url"],
    )
    temp_file.write_text(valid_basic_conn_config_contents)
    parsed_config = schema.parse_connection_yaml(temp_file, (ConnectionEnvironment.DRAFT,))
    draft_config = parsed_config[0]
    assert isinstance(draft_config, schema.ExtendedConnectionConfiguration)
    assert isinstance(draft_config.credentials, BasicAuthCredentials)
    # update published app_id in test data and check equivalence
    test_data.update({"app_id": published_app_id(test_data["app_id"])})
    assert (
        draft_config.credentials.username
        == test_data["environments"]["draft"]["credentials"]["username"]
    )
    assert (
        draft_config.credentials.password
        == test_data["environments"]["draft"]["credentials"]["password"]
    )
    assert draft_config.kind == test_data["environments"]["draft"]["kind"]
    assert draft_config.server_url == test_data["environments"]["draft"]["server_url"]


def test_parse_invalid_basic_conn_yaml(tmp_path: Path) -> None:
    """
    Tests parsing of an invalid 'basic' auth connection config YAML file.

    Args:
        tmp_path: tmp path used to write test YAML files.
    """
    test_data: dict[str, Any] = {
        "spec_version": "v1",
        "kind": "connection",
        "app_id": "invalid_basic_auth",
        "environments": {
            "draft": {
                "kind": "basic",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {"username": "test_username", "password": "test_password"},
            },
            "live": {
                "kind": "basic",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {"username": "test_username", "password": "test_password"},
            },
        },
    }

    invalid_basic_auth_yaml_template = """
    spec_version: v1
    kind: connection
    app_id: "{app_id}"
    environments:
        draft:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                username: "{username}"
        live:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                username: "{username}"
    """
    temp_file = tmp_path / "test_invalid_basic_conn.yaml"
    invalid_basic_conn_config_contents = invalid_basic_auth_yaml_template.format(
        app_id=test_data["app_id"],
        kind=test_data["environments"]["draft"]["kind"],
        username=test_data["environments"]["draft"]["credentials"]["username"],
        password=test_data["environments"]["draft"]["credentials"]["password"],
        server_url=test_data["environments"]["draft"]["server_url"],
    )
    temp_file.write_text(invalid_basic_conn_config_contents)
    with pytest.raises(ValidationError):
        # missing 'password'
        schema.parse_connection_yaml(temp_file, (ConnectionEnvironment.DRAFT,))


def test_parse_valid_bearer_conn_yaml(tmp_path: Path) -> None:
    """
    Tests parsing of a valid 'bearer' auth connection config YAML file.

    Args:
        tmp_path: tmp path used to write test YAML files.
    """
    test_data: dict[str, Any] = {
        "spec_version": "v1",
        "kind": "connection",
        "app_id": "test_bearer_app_id",
        "environments": {
            "draft": {
                "kind": "bearer",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {"token": "test_token"},
            },
            "live": {
                "kind": "bearer",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {"token": "test_token"},
            },
        },
    }

    valid_bearer_auth_yaml_template = """
    spec_version: v1
    kind: connection
    app_id: "{app_id}"
    environments:
        draft:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                token: "{token}"
        live:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                token: "{token}"
    """
    temp_file = tmp_path / "test_valid_bearer_conn.yaml"
    valid_bearer_conn_config_contents = valid_bearer_auth_yaml_template.format(
        app_id=test_data["app_id"],
        kind=test_data["environments"]["draft"]["kind"],
        token=test_data["environments"]["draft"]["credentials"]["token"],
        server_url=test_data["environments"]["draft"]["server_url"],
    )
    temp_file.write_text(valid_bearer_conn_config_contents)
    parsed_config = schema.parse_connection_yaml(temp_file, (ConnectionEnvironment.DRAFT,))
    draft_config = parsed_config[0]
    assert isinstance(draft_config, schema.ExtendedConnectionConfiguration)
    assert isinstance(draft_config.credentials, BearerTokenAuthCredentials)
    # update published app_id in test data and check equivalence
    test_data.update({"app_id": published_app_id(test_data["app_id"])})
    assert (
        draft_config.credentials.token == test_data["environments"]["draft"]["credentials"]["token"]
    )
    assert draft_config.kind == test_data["environments"]["draft"]["kind"]
    assert draft_config.server_url == test_data["environments"]["draft"]["server_url"]


def test_parse_invalid_bearer_conn_yaml(tmp_path: Path) -> None:
    """
    Tests parsing of an invalid 'bearer' auth connection config YAML file.

    Args:
        tmp_path: tmp path used to write test YAML files.
    """
    test_data: dict[str, Any] = {
        "spec_version": "v1",
        "kind": "connection",
        "app_id": "test_bearer_app_id",
        "environments": {
            "draft": {
                "kind": "bearer",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {"token": "test_token"},
            },
            "live": {
                "kind": "bearer",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {"token": "test_token"},
            },
        },
    }

    invalid_bearer_auth_yaml_template = """
    spec_version: v1
    kind: connection
    app_id: "{app_id}"
    environments:
        draft:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                username: "{token}"
        live:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                username: "{token}"
    """
    temp_file = tmp_path / "test_valid_bearer_conn.yaml"
    invalid_bearer_conn_config_contents = invalid_bearer_auth_yaml_template.format(
        app_id=test_data["app_id"],
        kind=test_data["environments"]["draft"]["kind"],
        token=test_data["environments"]["draft"]["credentials"]["token"],
        server_url=test_data["environments"]["draft"]["server_url"],
    )
    temp_file.write_text(invalid_bearer_conn_config_contents)
    with pytest.raises(ValidationError):
        # missing 'token'
        schema.parse_connection_yaml(temp_file, (ConnectionEnvironment.DRAFT,))


def test_parse_valid_key_value_conn_yaml(tmp_path: Path) -> None:
    """
    Tests parsing of a valid 'key_value' auth connection config YAML file.

    Args:
        tmp_path: tmp path used to write test YAML files.
    """
    test_data: dict[str, Any] = {
        "app_id": "test_basic_app_id",
        "kind": "key_value",
        "key_values": {"key1": "val1", "key2": "val2"},
    }
    valid_key_value_auth_yaml_template = """
    spec_version: v1
    kind: connection
    app_id: "{app_id}"
    environments:
        draft:
            kind: "{kind}"
            type: team
            sso: false
            credentials:
                "key1": "{key1}"
                "key2": "{key2}"
        live:
            kind: "{kind}"
            type: team
            sso: false
            credentials:
                "key1": "{key1}"
                "key2": "{key2}"
    """
    valid_key_value_conn_config_contents = valid_key_value_auth_yaml_template.format(
        app_id=test_data["app_id"],
        kind=test_data["kind"],
        key1=test_data["key_values"]["key1"],
        key2=test_data["key_values"]["key2"],
    )
    temp_file = tmp_path / "test_valid_kv_conn.yaml"
    temp_file.write_text(valid_key_value_conn_config_contents)
    parsed_config = schema.parse_connection_yaml(temp_file, (ConnectionEnvironment.DRAFT,))
    draft_config = parsed_config[0]
    assert isinstance(draft_config, schema.ExtendedConnectionConfiguration)
    assert isinstance(draft_config.credentials, KeyValueConnectionCredentials)
    # update published app_id in test data and check equivalence
    test_data.update({"app_id": published_app_id(test_data["app_id"])})
    assert draft_config.credentials == test_data["key_values"]
    assert draft_config.kind == test_data["kind"]


def test_parse_invalid_key_value_conn_yaml(tmp_path: Path) -> None:
    """
    Tests parsing of an invalid 'key_value' auth connection config YAML file.

    Args:
        tmp_path: tmp path used to write test YAML files.
    """
    test_data: dict[str, Any] = {
        "app_id": "test_basic_app_id",
        "kind": "key_value",
        "key_values": {"key1": "val1", "key2": "val2"},
    }

    invalid_key_value_auth_yaml_template = """
    spec_version: v1
    kind: connection
    app_id: "{app_id}"
    environments:
        draft:
            kind: "{kind}"
            type: team
            sso: false
            credentials:
        live:
            kind: "{kind}"
            type: team
            sso: false
            credentials:
    """
    temp_file = tmp_path / "test_invalid_kv_conn.yaml"
    invalid_key_value_conn_config_contents = invalid_key_value_auth_yaml_template.format(
        app_id=test_data["app_id"], kind=test_data["kind"]
    )
    temp_file.write_text(invalid_key_value_conn_config_contents)
    with pytest.raises(ValidationError):
        # missing 'key_values'
        schema.parse_connection_yaml(temp_file, (ConnectionEnvironment.DRAFT,))


def test_parse_valid_api_key_conn_yaml(tmp_path: Path) -> None:
    """
    Tests parsing of a valid 'api_key' auth connection config YAML file.

    Args:
        tmp_path: tmp path used to write test YAML files.
    """
    test_data: dict[str, Any] = {
        "spec_version": "v1",
        "kind": "connection",
        "app_id": "test_api_key_app_id",
        "environments": {
            "draft": {
                "kind": "api_key",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {"api_key": "test_api_key"},
            },
            "live": {
                "kind": "api_key",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {"api_key": "test_api_key"},
            },
        },
    }

    valid_api_key_auth_yaml_template = """
    spec_version: v1
    kind: connection
    app_id: "{app_id}"
    environments:
        draft:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                api_key: "{api_key}"
        live:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                api_key: "{api_key}"
    """
    temp_file = tmp_path / "test_valid_api_key_conn.yaml"
    valid_api_key_conn_config_contents = valid_api_key_auth_yaml_template.format(
        app_id=test_data["app_id"],
        kind=test_data["environments"]["draft"]["kind"],
        api_key=test_data["environments"]["draft"]["credentials"]["api_key"],
        server_url=test_data["environments"]["draft"]["server_url"],
    )
    temp_file.write_text(valid_api_key_conn_config_contents)
    parsed_config = schema.parse_connection_yaml(temp_file, (ConnectionEnvironment.DRAFT,))
    draft_config = parsed_config[0]
    assert isinstance(draft_config, schema.ExtendedConnectionConfiguration)
    assert isinstance(draft_config.credentials, APIKeyAuthCredentials)
    # update published app_id in test data and check equivalence
    test_data.update({"app_id": published_app_id(test_data["app_id"])})
    assert (
        draft_config.credentials.api_key
        == test_data["environments"]["draft"]["credentials"]["api_key"]
    )
    assert draft_config.kind == test_data["environments"]["draft"]["kind"]
    assert draft_config.server_url == test_data["environments"]["draft"]["server_url"]


def test_parse_invalid_api_key_conn_yaml(tmp_path: Path) -> None:
    """
    Tests parsing of an invalid 'api_key' auth connection config YAML file.

    Args:
        tmp_path: tmp path used to write test YAML files.
    """
    test_data: dict[str, Any] = {
        "spec_version": "v1",
        "kind": "connection",
        "app_id": "test_api_key_app_id",
        "environments": {
            "draft": {
                "kind": "api_key",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {"api_key": "test_api_key"},
            },
            "live": {
                "kind": "api_key",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {"api_key": "test_api_key"},
            },
        },
    }

    invalid_api_key_auth_yaml_template = """
    spec_version: v1
    kind: connection
    app_id: "{app_id}"
    environments:
        draft:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
        live:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
    """
    temp_file = tmp_path / "test_invalid_api_key_conn.yaml"
    invalid_api_key_conn_config_contents = invalid_api_key_auth_yaml_template.format(
        app_id=test_data["app_id"],
        kind=test_data["kind"],
        api_key=test_data["environments"]["draft"]["credentials"]["api_key"],
        server_url=test_data["environments"]["draft"]["server_url"],
    )
    temp_file.write_text(invalid_api_key_conn_config_contents)
    with pytest.raises(ValidationError):
        # missing 'api_key'
        schema.parse_connection_yaml(temp_file, (ConnectionEnvironment.DRAFT,))


def test_parse_valid_oauth2_auth_code_conn_yaml(tmp_path: Path) -> None:
    """
    Tests parsing of a valid 'oauth_auth_code_flow' connection config YAML file.

    Args:
        tmp_path: tmp path used to write test YAML files.
    """
    test_data: dict[str, Any] = {
        "spec_version": "v1",
        "kind": "connection",
        "app_id": "test_oauth2_auth_code_app_id",
        "environments": {
            "draft": {
                "kind": "oauth_auth_code_flow",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {
                    "token_url": "test_token_url",
                    "authorization_url": "test_authorization_url",
                    "client_id": "test_client_id",
                    "client_secret": "test_client_secret",
                },
            },
            "live": {
                "kind": "oauth_auth_code_flow",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {
                    "token_url": "test_token_url",
                    "authorization_url": "test_authorization_url",
                    "client_id": "test_client_id",
                    "client_secret": "test_client_secret",
                },
            },
        },
    }

    valid_oauth2_auth_code_flow_yaml_template = """
    spec_version: v1
    kind: connection
    app_id: "{app_id}"
    environments:
        draft:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                    "token_url": "{token_url}"
                    "authorization_url": "{authorization_url}"
                    "client_id": "{client_id}"
                    "client_secret": "{client_secret}"
        live:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                    "token_url": "{token_url}"
                    "authorization_url": "{authorization_url}"
                    "client_id": "{client_id}"
                    "client_secret": "{client_secret}"
    """
    temp_file = tmp_path / "test_valid_oauth2_auth_code_flow_conn.yaml"
    valid_api_key_conn_config_contents = valid_oauth2_auth_code_flow_yaml_template.format(
        app_id=test_data["app_id"],
        kind=test_data["environments"]["draft"]["kind"],
        token_url=test_data["environments"]["draft"]["credentials"]["token_url"],
        authorization_url=test_data["environments"]["draft"]["credentials"]["authorization_url"],
        client_id=test_data["environments"]["draft"]["credentials"]["client_id"],
        client_secret=test_data["environments"]["draft"]["credentials"]["client_secret"],
        server_url=test_data["environments"]["draft"]["server_url"],
    )
    temp_file.write_text(valid_api_key_conn_config_contents)
    parsed_config = schema.parse_connection_yaml(temp_file, (ConnectionEnvironment.DRAFT,))
    draft_config = parsed_config[0]
    assert isinstance(draft_config, schema.ExtendedConnectionConfiguration)
    assert isinstance(draft_config.credentials, OAuth2AuthCodeCredentials)
    # update published app_id in test data and check equivalence
    test_data.update({"app_id": published_app_id(test_data["app_id"])})
    assert (
        draft_config.credentials.token_url
        == test_data["environments"]["draft"]["credentials"]["token_url"]
    )
    assert (
        draft_config.credentials.authorization_url
        == test_data["environments"]["draft"]["credentials"]["authorization_url"]
    )
    assert (
        draft_config.credentials.client_id
        == test_data["environments"]["draft"]["credentials"]["client_id"]
    )
    assert (
        draft_config.credentials.client_secret
        == test_data["environments"]["draft"]["credentials"]["client_secret"]
    )
    assert draft_config.kind == test_data["environments"]["draft"]["kind"]
    assert draft_config.server_url == test_data["environments"]["draft"]["server_url"]


def test_parse_invalid_oauth2_auth_code_conn_yaml(tmp_path: Path) -> None:
    """
    Tests parsing of an invalid 'oauth_auth_code_flow' connection config YAML file.

    Args:
        tmp_path: tmp path used to write test YAML files.
    """
    test_data: dict[str, Any] = {
        "spec_version": "v1",
        "kind": "connection",
        "app_id": "test_api_key_app_id",
        "environments": {
            "draft": {
                "kind": "oauth_auth_code_flow",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {"token_url": "test_token_url"},
            },
            "live": {
                "kind": "oauth_auth_code_flow",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {"token_url": "test_token_url"},
            },
        },
    }

    invalid_oauth2_auth_code_flow_yaml_template = """
    spec_version: v1
    kind: connection
    app_id: "{app_id}"
    environments:
        draft:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                    "token_url": "{token_url}"
        live:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                    "token_url": "{token_url}"
    """
    temp_file = tmp_path / "test_invalid_oauth2_auth_code_flow_conn.yaml"
    invalid_oauth2_auth_code_conn_config_contents = (
        invalid_oauth2_auth_code_flow_yaml_template.format(
            app_id=test_data["app_id"],
            kind=test_data["kind"],
            token_url=test_data["environments"]["draft"]["credentials"]["token_url"],
            server_url=test_data["environments"]["draft"]["server_url"],
        )
    )
    temp_file.write_text(invalid_oauth2_auth_code_conn_config_contents)
    with pytest.raises(ValidationError):
        # missing 'authorization_url', 'client_id', and 'client_secet'
        schema.parse_connection_yaml(temp_file, (ConnectionEnvironment.DRAFT,))


def test_parse_valid_oauth2_client_credentials_conn_yaml(tmp_path: Path) -> None:
    """
    Tests parsing of a valid 'oauth_auth_client_credentials_flow' connection config YAML file.

    Args:
        tmp_path: tmp path used to write test YAML files.
    """
    test_data: dict[str, Any] = {
        "spec_version": "v1",
        "kind": "connection",
        "app_id": "test_oauth2_client_credentials_app_id",
        "environments": {
            "draft": {
                "kind": "oauth_auth_client_credentials_flow",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {
                    "token_url": "test_token_url",
                    "client_id": "test_client_id",
                    "client_secret": "test_client_secret",
                },
            },
            "live": {
                "kind": "oauth_auth_client_credentials_flow",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {
                    "token_url": "test_token_url",
                    "client_id": "test_client_id",
                    "client_secret": "test_client_secret",
                },
            },
        },
    }

    valid_oauth2_client_credentials_flow_yaml_template = """
    spec_version: v1
    kind: connection
    app_id: "{app_id}"
    environments:
        draft:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                    "token_url": "{token_url}"
                    "client_id": "{client_id}"
                    "client_secret": "{client_secret}"
        live:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                    "token_url": "{token_url}"
                    "client_id": "{client_id}"
                    "client_secret": "{client_secret}"
    """
    temp_file = tmp_path / "test_valid_oauth2_client_credentials_flow_conn.yaml"
    valid_api_key_conn_config_contents = valid_oauth2_client_credentials_flow_yaml_template.format(
        app_id=test_data["app_id"],
        kind=test_data["environments"]["draft"]["kind"],
        token_url=test_data["environments"]["draft"]["credentials"]["token_url"],
        client_id=test_data["environments"]["draft"]["credentials"]["client_id"],
        client_secret=test_data["environments"]["draft"]["credentials"]["client_secret"],
        server_url=test_data["environments"]["draft"]["server_url"],
    )
    temp_file.write_text(valid_api_key_conn_config_contents)
    parsed_config = schema.parse_connection_yaml(temp_file, (ConnectionEnvironment.DRAFT,))
    draft_config = parsed_config[0]
    assert isinstance(draft_config, schema.ExtendedConnectionConfiguration)
    assert isinstance(draft_config.credentials, OAuth2ClientCredentials)
    # update published app_id in test data and check equivalence
    test_data.update({"app_id": published_app_id(test_data["app_id"])})
    assert (
        draft_config.credentials.token_url
        == test_data["environments"]["draft"]["credentials"]["token_url"]
    )
    assert (
        draft_config.credentials.client_id
        == test_data["environments"]["draft"]["credentials"]["client_id"]
    )
    assert (
        draft_config.credentials.client_secret
        == test_data["environments"]["draft"]["credentials"]["client_secret"]
    )
    assert draft_config.kind == test_data["environments"]["draft"]["kind"]
    assert draft_config.server_url == test_data["environments"]["draft"]["server_url"]


def test_parse_invalid_oauth2_client_credentials_conn_yaml(tmp_path: Path) -> None:
    """
    Tests parsing of an invalid 'oauth_auth_client_credentials_flow' connection config YAML file.

    Args:
        tmp_path: tmp path used to write test YAML files.
    """
    test_data: dict[str, Any] = {
        "spec_version": "v1",
        "kind": "connection",
        "app_id": "test_api_key_app_id",
        "environments": {
            "draft": {
                "kind": "oauth_auth_client_credentials_flow",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {"token_url": "test_token_url"},
            },
            "live": {
                "kind": "oauth_auth_client_credentials_flow",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {"token_url": "test_token_url"},
            },
        },
    }

    invalid_oauth2_client_credentials_flow_yaml_template = """
    spec_version: v1
    kind: connection
    app_id: "{app_id}"
    environments:
        draft:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                    "token_url": "{token_url}"
        live:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                    "token_url": "{token_url}"
    """
    temp_file = tmp_path / "test_invalid_oauth2_client_credentials_flow_conn.yaml"
    invalid_oauth2_client_credentials_conn_config_contents = (
        invalid_oauth2_client_credentials_flow_yaml_template.format(
            app_id=test_data["app_id"],
            kind=test_data["kind"],
            token_url=test_data["environments"]["draft"]["credentials"]["token_url"],
            server_url=test_data["environments"]["draft"]["server_url"],
        )
    )
    temp_file.write_text(invalid_oauth2_client_credentials_conn_config_contents)
    with pytest.raises(ValidationError):
        # missing 'client_id', and 'client_secet'
        schema.parse_connection_yaml(temp_file, (ConnectionEnvironment.DRAFT,))


def test_parse_valid_oauth2_password_conn_yaml(tmp_path: Path) -> None:
    """
    Tests parsing of a valid 'oauth_auth_password_flow' connection config YAML file.

    Args:
        tmp_path: tmp path used to write test YAML files.
    """
    test_data: dict[str, Any] = {
        "spec_version": "v1",
        "kind": "connection",
        "app_id": "test_oauth2_password_app_id",
        "environments": {
            "draft": {
                "kind": "oauth_auth_password_flow",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {
                    "token_url": "test_token_url",
                    "client_id": "test_client_id",
                    "client_secret": "test_client_secret",
                    "username": "test_username",
                    "password": "test_password",
                },
            },
            "live": {
                "kind": "oauth_auth_password_flow",
                "type": "team",
                "sso": False,
                "server_url": "test_url",
                "credentials": {
                    "token_url": "test_token_url",
                    "client_id": "test_client_id",
                    "client_secret": "test_client_secret",
                    "username": "test_username",
                    "password": "test_password",
                },
            },
        },
    }

    valid_oauth2_password_flow_yaml_template = """
    spec_version: v1
    kind: connection
    app_id: "{app_id}"
    environments:
        draft:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                    "token_url": "{token_url}"
                    "client_id": "{client_id}"
                    "client_secret": "{client_secret}"
                    "username": "{username}"
                    "password": "{password}"
        live:
            kind: "{kind}"
            type: team
            sso: false
            server_url: "{server_url}"
            credentials:
                    "token_url": "{token_url}"
                    "client_id": "{client_id}"
                    "client_secret": "{client_secret}"
                    "username": "{username}"
                    "password": "{password}"
    """
    temp_file = tmp_path / "test_valid_oauth2_password_flow_conn.yaml"
    valid_oauth_password_conn_config_contents = valid_oauth2_password_flow_yaml_template.format(
        app_id=test_data["app_id"],
        kind=test_data["environments"]["draft"]["kind"],
        server_url=test_data["environments"]["draft"]["server_url"],
        token_url=test_data["environments"]["draft"]["credentials"]["token_url"],
        client_id=test_data["environments"]["draft"]["credentials"]["client_id"],
        client_secret=test_data["environments"]["draft"]["credentials"]["client_secret"],
        username=test_data["environments"]["draft"]["credentials"]["username"],
        password=test_data["environments"]["draft"]["credentials"]["password"],
    )
    temp_file.write_text(valid_oauth_password_conn_config_contents)
    parsed_config = schema.parse_connection_yaml(temp_file, (ConnectionEnvironment.DRAFT,))
    draft_config = parsed_config[0]
    assert isinstance(draft_config, schema.ExtendedConnectionConfiguration)
    assert isinstance(draft_config.credentials, OAuth2PasswordCredentials)
    # update published app_id in test data and check equivalence
    test_data.update({"app_id": published_app_id(test_data["app_id"])})
    assert (
        draft_config.credentials.token_url
        == test_data["environments"]["draft"]["credentials"]["token_url"]
    )
    assert (
        draft_config.credentials.client_id
        == test_data["environments"]["draft"]["credentials"]["client_id"]
    )
    assert (
        draft_config.credentials.client_secret
        == test_data["environments"]["draft"]["credentials"]["client_secret"]
    )
    assert (
        draft_config.credentials.username
        == test_data["environments"]["draft"]["credentials"]["username"]
    )
    assert (
        draft_config.credentials.password
        == test_data["environments"]["draft"]["credentials"]["password"]
    )
    assert draft_config.kind == test_data["environments"]["draft"]["kind"]
    assert draft_config.server_url == test_data["environments"]["draft"]["server_url"]
