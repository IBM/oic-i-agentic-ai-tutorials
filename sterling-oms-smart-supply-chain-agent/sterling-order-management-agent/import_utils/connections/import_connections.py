import glob
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from connections import schema
from ibm_watsonx_orchestrate.agent_builder.connections.types import (
    OAUTH_CONNECTION_TYPES,
    APIKeyAuthCredentials,
    BasicAuthCredentials,
    BearerTokenAuthCredentials,
    ConnectionEnvironment,
    KeyValueConnectionCredentials,
    OAuth2AuthCodeCredentials,
    OAuth2ClientCredentials,
    OAuth2PasswordCredentials,
    OAuthOnBehalfOfCredentials,
)
from ibm_watsonx_orchestrate.cli.commands.connections.connections_controller import (
    add_configuration,
    add_connection,
    add_credentials,
)
from ibm_watsonx_orchestrate.client.connections import get_connection_type, get_connections_client
from import_utils.connections.tools_app_id_mapper import ConnectionsToolMapper
from import_utils.utils.directory import find_target_directory
from import_utils.utils.logger import get_logger
import typer
from typing_extensions import Annotated

from agent_ready_tools.utils.tool_credentials import published_app_id

LOGGER = get_logger(__name__)
app = typer.Typer(help="Import the connections given as arguments.")

type ConnectionsIds = Optional[List[str]]
type TargetConnectionsMap = Dict[str, Optional[List[str]]]


class ConnectionManager:
    """Manages connections for orchestrate."""

    connection_configs: Dict[str, List[schema.ExtendedConnectionConfiguration]]
    _creds_path: Path
    force_conns_import: bool

    def __init__(
        self,
        connection_configs: Optional[
            Dict[str, List[schema.ExtendedConnectionConfiguration]]
        ] = None,
        force_conns_import: bool = False,
        envs_to_parse: Tuple[ConnectionEnvironment] = (ConnectionEnvironment.DRAFT,),
    ) -> None:
        """
        Build all data needed for connections.

        Args:
            connection_configs: Map of conn-id names to ConnectionConfig objects built from yamls.
            force_conns_import: Put manager is a state to reinitialize existing connections.
            envs_to_parse: Tuple of environemnts that should be parsed
        """
        self.connection_configs = (
            connection_configs
            if connection_configs
            else self._build_connection_configs_from_repo(envs_to_parse)
        )
        self.force_conns_import = force_conns_import

    def _build_connection_configs_from_repo(
        self, envs_to_parse: Tuple[ConnectionEnvironment]
    ) -> Dict[str, List[schema.ExtendedConnectionConfiguration]]:
        """
        Build ConnectionConfig from files in the repository.

        Args:
            envs_to_parse: Tuple of environemnts that should be parsed

        Returns:
            ConnectionConfig objects built from yamls.
        """

        connection_configs = dict()

        agent_ready_tools_dir = find_target_directory("agent_ready_tools")
        repo = agent_ready_tools_dir.parent
        self._creds_path = agent_ready_tools_dir / "utils" / "credentials.json"

        configs_folder = repo / "connections" / "configs"
        for cfg_dir in configs_folder.iterdir():
            if not cfg_dir.is_dir() or "templates" in str(cfg_dir):
                continue
            connection_yamls = glob.glob(str(cfg_dir / "*.yaml"))
            for file in connection_yamls:
                conns: List[schema.ExtendedConnectionConfiguration] = schema.parse_connection_yaml(
                    file, envs_to_parse
                )
                if conns:
                    connection_configs[conns[0].app_id] = conns
        return connection_configs

    @property
    def supported_connections(self) -> set:
        """
        Helper for bash script to list all available connections.

        Returns:
            set of supported connections
        """
        return set(self.connection_configs.keys())

    def _fill_secrets(
        self, conn: schema.ExtendedConnectionConfiguration
    ) -> schema.ExtendedConnectionConfiguration:
        """
        Replaces secrtes placeholders with actual values.

        Args:
            conn: Connection object.

        Returns:
            connection config for importing
        """

        _creds_json: dict = {}
        with open(self._creds_path) as creds:
            _creds_json = json.load(creds)

        if conn.server_url:
            conn.server_url = conn.server_url.format(**_creds_json)
        conn.credentials = self._interpolate_credentials(conn.credentials)
        return conn

    def _interpolate_credentials(
        self,
        credentials: Union[
            BasicAuthCredentials,
            BearerTokenAuthCredentials,
            APIKeyAuthCredentials,
            KeyValueConnectionCredentials,
            OAuth2AuthCodeCredentials,
            OAuth2ClientCredentials,
            OAuthOnBehalfOfCredentials,
            OAuth2PasswordCredentials,
        ],
    ) -> Union[
        BasicAuthCredentials,
        BearerTokenAuthCredentials,
        APIKeyAuthCredentials,
        KeyValueConnectionCredentials,
        OAuth2AuthCodeCredentials,
        OAuth2ClientCredentials,
        OAuthOnBehalfOfCredentials,
        OAuth2PasswordCredentials,
    ]:
        """
        Replace secretes placeholders in credentials with actual values.

        Args:
            credentials: Credentials object to replace secrets in

        Returns:
            same Credentials object but with real values
        """
        with open(self._creds_path) as f:
            secrets = json.load(f)

        # Create a new dictionary with interpolated values
        updated_data: dict[str, Any] = {}

        for field_name, value in credentials.model_dump().items():
            if isinstance(value, str):
                updated_data[field_name] = value.format(**secrets)
            elif isinstance(value, dict):
                updated_data[field_name] = {
                    k: v.format(**secrets) if isinstance(v, str) else v for k, v in value.items()
                }
            else:
                updated_data[field_name] = value  # leave untouched if not str or dict

        # Re-instantiate the same credentials class with updated values
        return credentials.__class__(**updated_data)

    def _import_connections(self, connection_args: Tuple[str, ...]) -> None:
        """
        Imports the given list of connections (app-ids) from the defined configs into the SDK
        server.

        Args:
            connection_args: App-ids passed into the import_connections script with the
                --connections arg.
        """
        client = get_connections_client()
        connections = client.list()
        existing_app_ids = [c.app_id for c in connections]

        for app_id in connection_args:
            if app_id in existing_app_ids and not self.force_conns_import:
                LOGGER.info(f"Skipping creating existing connection with app-id: {app_id}...")
                continue

            conns = self.connection_configs.get(app_id)
            assert conns, f"Connection config with app-id {app_id} not found."

            for conn in conns:
                # create conn if it doesn't yet exist
                if app_id not in existing_app_ids:
                    add_connection(app_id=app_id)

                conn = self._fill_secrets(conn)
                add_configuration(conn.to_base_connection_config())

                # figure out if this connection uses 'app_credentials' (for Oauth2 apps)
                # see wxo-client: connections_controller.py: set_credentials_connection()
                # TODO: use higher level ADK functionality instead of duplicating this logic:
                # https://github.ibm.com/WatsonOrchestrate/wxo-domains/issues/8128
                conn_type = get_connection_type(
                    security_scheme=conn.security_scheme, auth_type=conn.auth_type
                )
                use_app_credentials = conn_type in OAUTH_CONNECTION_TYPES
                add_credentials(
                    app_id=conn.app_id,
                    environment=conn.environment,
                    use_app_credentials=use_app_credentials,
                    credentials=conn.credentials,
                )

    def import_all_connections(self) -> None:
        """Public accessing method for building all available connections."""
        self._import_connections(tuple(self.connection_configs))

    def import_connections(self, connections: Tuple[str, ...]) -> None:
        """Public accessing method for building selected connections."""
        assert (
            conn in self.supported_connections for conn in connections
        ), f"One or more unsupported connections: {connections}. To see list of available connections use --supported_connections."

        self._import_connections(connections)

    def configure_connections_for_tools(
        self,
        targeted_tools: Optional[List[str]],
        resume_import: bool = False,
    ) -> tuple[ConnectionsIds, TargetConnectionsMap]:
        """
        Build the connections app_ids list for tools being imported. Import connections if found,
        unless specified to skip importing.

        Args:
            targeted_tools: The list of tools we want to specifically import into orchestrate
            resume_import: If resume_import process, then skip connections building.

        Returns:
            The list of connections app_ids or None if not available.
        """
        conn_ids: Optional[List[str]]
        targeted_conn_id_map: Dict[str, Optional[List[str]]] = {}

        if targeted_tools:
            conn_mapper = ConnectionsToolMapper()
            for target_tool_name in targeted_tools:
                specific_conn_id_list: Optional[List[str]] = list(
                    conn_mapper.tool_name_to_app_id_map.get(target_tool_name, set())
                )
                if not specific_conn_id_list:  # targeted_tools don't use imported connections.
                    # Mimic CLI Usage: Explicitly pass in None into tool_import if no app-ids are found.
                    specific_conn_id_list = None
                targeted_conn_id_map[target_tool_name] = specific_conn_id_list

            # To be used in the building of connections. Make sure we have a list of unique elements
            conn_ids = list(
                {
                    app_id
                    for conn_list in targeted_conn_id_map.values()
                    if conn_list is not None
                    for app_id in conn_list
                }
            )
        else:
            conn_ids = list(self.supported_connections)

        if conn_ids and not resume_import:
            self.import_connections(tuple(conn_ids))

        # TODO: remove conn_ids from return, doesn't seem to be used.
        return conn_ids, targeted_conn_id_map


@app.command()
def main(
    connections: Annotated[
        Optional[List[str]],
        typer.Option(
            "-c",
            "--connections",
            help="Specify which connections to import into SDK server. By default, will import everything.",
        ),
    ] = None,
    supported_connections: Annotated[
        bool,
        typer.Option(
            "--supported_connections",
            help="Helper for the import script to list defined connections.",
        ),
    ] = False,
    force_import_connections: Annotated[
        bool,
        typer.Option(
            "--force_import_connections",
            help="Force import connections for orchestrate. If a required connection exists, it will be reconfigured and have its credentials re-set.",
        ),
    ] = False,
    environments_to_import: Annotated[
        Optional[List[ConnectionEnvironment]],
        typer.Option(
            "--environments_to_import",
            help="List with environments that should be imported",
        ),
    ] = None,
) -> None:
    """Exports all of agent_ready_tools as a single Python file (dependencies not included)."""

    if not environments_to_import:
        environments_to_import = [ConnectionEnvironment.DRAFT]
    if not connections:
        connections = ["all"]

    conn_manager = ConnectionManager(
        force_conns_import=force_import_connections, envs_to_parse=tuple(environments_to_import)
    )

    # TODO: remove this and any code used for bash ingestion.
    if supported_connections:
        print(" ".join(list(conn_manager.supported_connections)))
        sys.exit(0)

    if connections == ["all"]:
        conn_manager.import_all_connections()
    else:
        # import specified connections with publisher suffix appended
        conn_manager.import_connections(tuple(published_app_id(c) for c in connections))


if __name__ == "__main__":
    app()
