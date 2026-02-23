from pathlib import Path
from typing import List, Tuple, Union

from ibm_watsonx_orchestrate.agent_builder.connections.types import (
    APIKeyAuthCredentials,
    BasicAuthCredentials,
    BearerTokenAuthCredentials,
    ConnectionConfiguration,
    ConnectionEnvironment,
    ConnectionKind,
    KeyValueConnectionCredentials,
    OAuth2AuthCodeCredentials,
    OAuth2ClientCredentials,
    OAuth2PasswordCredentials,
    OAuthOnBehalfOfCredentials,
)
from pydantic import ConfigDict, field_validator, model_validator
import yaml

from agent_ready_tools.utils.tool_credentials import published_app_id

CREDENTIALS_KIND_TO_CLASS = {
    ConnectionKind.basic: BasicAuthCredentials,
    ConnectionKind.bearer: BearerTokenAuthCredentials,
    ConnectionKind.api_key: APIKeyAuthCredentials,
    ConnectionKind.key_value: KeyValueConnectionCredentials,
    ConnectionKind.oauth_auth_code_flow: OAuth2AuthCodeCredentials,
    ConnectionKind.oauth_auth_client_credentials_flow: OAuth2ClientCredentials,
    ConnectionKind.oauth_auth_on_behalf_of_flow: OAuthOnBehalfOfCredentials,
    ConnectionKind.oauth_auth_password_flow: OAuth2PasswordCredentials,
}


class ExtendedConnectionConfiguration(ConnectionConfiguration):
    """Represents ConnectionConfiguration class with added credentials data."""

    app_id: str
    kind: str
    credentials: Union[
        BasicAuthCredentials,
        BearerTokenAuthCredentials,
        APIKeyAuthCredentials,
        KeyValueConnectionCredentials,
        OAuth2AuthCodeCredentials,
        OAuth2ClientCredentials,
        OAuthOnBehalfOfCredentials,
        OAuth2PasswordCredentials,
    ]
    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    @field_validator("app_id", mode="before")
    @classmethod
    def apply_published_app_id(cls, value: str) -> str:
        """Appends IBM publisher suffix to app-id."""
        return published_app_id(value)

    @model_validator(mode="before")
    @classmethod
    def cast_credentials(cls, data: dict) -> dict:
        """Intercepts incoming data before field validation, and injects the correct credentials
        class based on `kind`."""
        kind = data.get("kind")
        credentials = data.get("credentials")

        if not kind or not credentials or not isinstance(credentials, dict):
            return data

        expected_class = CREDENTIALS_KIND_TO_CLASS.get(kind)
        if not expected_class:
            raise ValueError(f"Connection kind {kind} not supproted")
        # Manually cast the dict to the expected class
        data["credentials"] = expected_class(**credentials)

        return data

    def to_base_connection_config(self) -> ConnectionConfiguration:
        """
        Converts ExtendedConnectionConfiguration object to its parent class - ConnectionConfiguration

        Returns:
            ConnectionConfiguration
        """
        base_data = self.model_dump(
            exclude={"credentials", "kind"},
            exclude_none=True,  # ← removes fields explicitly set to None
        )
        return ConnectionConfiguration(**base_data)


def parse_connection_yaml(
    file: Union[Path, str], envs_to_parse: Tuple[ConnectionEnvironment, ...]
) -> List[ExtendedConnectionConfiguration]:
    """
    Parses a given YAML file into a ConnectionConfig object.

    Args:
        file: name of the connection yaml file.
        envs_to_parse: Tuple of environments that should be parsed

    Returns:
        ConnectionConfig corresponding to the yaml file.
    """
    with open(file, "r") as stream:
        try:
            yaml_dict: dict = yaml.safe_load(stream.read())
        except yaml.YAMLError as exc:
            raise ValueError(f"Failed to load connection YAML file '{file}': {exc}")

    connection_envs = yaml_dict.get("environments", {})
    app_id = yaml_dict.get("app_id")

    configs_to_add = []
    for env_to_parse in envs_to_parse:
        config = connection_envs.get(env_to_parse)
        config["environment"] = env_to_parse
        config["app_id"] = app_id

        # validate
        ConnectionConfiguration.model_validate(config)

        configs_to_add.append(ExtendedConnectionConfiguration(**config))

    return configs_to_add
