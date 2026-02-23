import os
from pathlib import Path
import shutil
import tempfile
from types import TracebackType
from typing import Any, List, Optional

from agent_validation.util import logger
from agent_validation.util.logger import get_logger
from ibm_watsonx_orchestrate.cli.commands.agents.agents_controller import AgentsController
from ibm_watsonx_orchestrate.cli.commands.environment.environment_command import activate_env
from ibm_watsonx_orchestrate.cli.commands.tools.tools_controller import ToolKind, ToolsController
from ibm_watsonx_orchestrate.cli.config import PROTECTED_ENV_NAME
from import_utils.agent_importer.agent_import import import_agents
from import_utils.clear_env import clear_local_env
from import_utils.connections.import_connections import ConnectionManager, TargetConnectionsMap
from import_utils.import_command import (
    COLLABORATOR_REL_DIR,
    CREDENTIALS_REL_PATH,
    LITE_REQUIREMENTS_REL_PATH,
)
from import_utils.tool_importer.agent_yamls_data import AgentYamlsData
from import_utils.tool_importer.eval_patch_tools import eval_patch_tools_import
from import_utils.tool_importer.multifile_tools import multi_file_tool_import
import yaml

CREDS_JSON = "agent_ready_tools/utils/credentials.json"
_logger = get_logger(__name__)


class ImportManager:
    """A context manager that handles importing agents/tools for each test suite."""

    def __init__(
        self,
        manager_filepath: str,
        replacement_model: Optional[str] = None,
        env_setup: bool = True,
        env_cleanup: bool = True,
    ):
        """
        Args:
            manager_filepath: The path to the manager agent definition
            replacement_model: Optional model to replace the default model in agent definition.
            env_setup: Whether to perform setup during context entry. Defaults to True.
            env_cleanup: Whether to clean up tools/agents during context exit. Defaults to True.
            mock_data_file: Which mock data to r/w from. Defaults to None. Name of file within `mock_data/adk_vcr`

        """
        self.logger = logger.get_logger()

        self.manager_filepath = manager_filepath

        self.manager_yaml_data = AgentYamlsData(manager_filepath=Path(manager_filepath))

        self.tool_client = ToolsController(
            tool_kind=ToolKind.python,
        )
        self.agent_client = AgentsController()
        self.native_client = self.agent_client.get_native_client()

        self.replacement_model = replacement_model

        self.env_setup = env_setup
        self.env_cleanup = env_cleanup
        self._list_agents_tools()

    def _list_agents_tools(self) -> None:
        """Prints all imported agents and tools, intended for debugging."""

        self.logger.debug(f"Tools imported: {self.tool_client.get_all_tools().keys()}")
        self.logger.debug(
            f"Agents imported: {self.agent_client.get_all_agents(self.native_client).keys()}"
        )

    def _replace_agent_model(self) -> None:
        """
        Makes a copy of the original agent files and update the llm with replacement_model.

        Import updated agents.
        """
        # create a tmp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            self.logger.info(
                f"Creating a temporary directory {tmpdir} to store agent definition with model {self.replacement_model}."
            )
            for agent_file in self.manager_yaml_data.get_topological_order_filepaths():
                shutil.copy(agent_file, tmpdir)

            # update agents to use replacement_model
            for agent_file in os.listdir(tmpdir):
                tmp_agent_file = os.path.join(tmpdir, agent_file)
                # replace llm field
                with open(tmp_agent_file, "r") as f:
                    data = yaml.safe_load(f)
                data["llm"] = self.replacement_model
                with open(tmp_agent_file, "w") as f:
                    yaml.dump(data, f, sort_keys=False)
                # import agent
                self.agent_client.publish_or_update_agents(
                    self.agent_client.import_agent(file=tmp_agent_file, app_id=None)
                )

    def import_env(self) -> None:
        """Imports agents and tools under the manager agent by calling the import command."""
        if self.env_setup:
            self.logger.info("Setting up environment.")

            # ensure credential file exists
            if not os.path.exists(CREDS_JSON):
                raise Exception(f"Can not find credential file at {CREDS_JSON}.")
            # the code will call another pants command
            os.environ["PANTS_CONCURRENT"] = "True"

            # Activate local env in orchestrate
            # Need to activate before the pants run so connections will be setup properly
            activate_env(name=PROTECTED_ENV_NAME)

            # calls import
            try:
                self._eval_import_command()
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.logger.error(f"Import command failed: {str(e)}")

            self._list_agents_tools()

        if self.replacement_model:
            self._replace_agent_model()

    def _cleanup(self) -> None:
        """Removes all tools/agents."""
        if not self.env_cleanup:
            return

        self.logger.info("Cleaning up.")
        clear_local_env(ignore_connections=True)

    def __enter__(self) -> None:
        """
        Enters the context.

        Import agents with replacement_model if it exists. Import agents/tools if env_setup is true
        """
        self.import_env()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """
        Exit the context. Removes agents/tools if env_cleanup is true.

        Args:
            exc_type: exception type, if raise
            exc_val: exception value
            exc_tb: traceback

        Returns:
            True
        """
        if exc_type:
            self.logger.error(f"An exception of type {exc_type} occurred: {exc_val}.\n{exc_tb}")
            return False

        self._cleanup()
        return True

    def _eval_import_command(
        self,
        collaborator_yaml_dir: Path = COLLABORATOR_REL_DIR,
        requirements_file: Path = LITE_REQUIREMENTS_REL_PATH,
        json_creds_file: Path = CREDENTIALS_REL_PATH,
    ) -> None:
        """
        Eval specific importing command.  Able to switch between standard importing and mocked
        connection.

        Args:
            collaborator_yaml_dir: Path to collaborator agents main
                directory.
            requirements_file: Path to the requirements_file.
            json_creds_file: Path to the credentials.json file
        """

        targeted_tools: List[str]

        _, targeted_tools = AgentYamlsData(
            manager_filepath=Path(self.manager_filepath)
        ).get_tool_dependencies()

        _, targeted_conn_id_map = ConnectionManager().configure_connections_for_tools(
            targeted_tools=targeted_tools,
        )

        assert json_creds_file.exists(), f"Credentials file not found. {json_creds_file}"

        assert requirements_file.exists(), f"Requirements file not found: {requirements_file}"

        multi_file_tool_import(
            requirements_file_path=requirements_file,
            targeted_conn_id_map=targeted_conn_id_map,
        )

        import_agents(
            collaborator_yaml_dir=collaborator_yaml_dir,
            domain=None,
            manager=Path(self.manager_filepath),
        )


class ImportPatchManager(ImportManager):
    """Import Manager Derivative for Tool Responses Patching."""

    patch_env: bool
    patch_file: Optional[Path]
    targeted_conn_id_map: TargetConnectionsMap

    def __init__(
        self,
        patch_env: bool = False,
        patch_file: Optional[Path] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Args:
            patch_env: Whether to patch tool responses in environment. Defaults to False. (From Config)
            patch_file: Str Path to the patch file.  Built from test case config path and passed in.
            args: Positional arguments passthrough for base class.
            kwargs: Keyword arguments passthrough for base class.
        """
        super().__init__(*args, **kwargs)
        self.patch_env = patch_env
        self.patch_file = patch_file

    def _setup_connections(self) -> None:
        """
        Setup connections for all tools. Should be done once.

        For Oauth2, they will be setup outside the framework, so this will only map the connections
        to the tools, but setup will be ignored by default since they exist.
        """
        targeted_tools: List[str]

        _, targeted_tools = AgentYamlsData(
            manager_filepath=Path(self.manager_filepath)
        ).get_tool_dependencies()

        if self.patch_env:
            self.targeted_conn_id_map = {t: None for t in targeted_tools}
        else:
            _, self.targeted_conn_id_map = ConnectionManager().configure_connections_for_tools(
                targeted_tools=targeted_tools,
            )

    def _eval_import_command(
        self,
        collaborator_yaml_dir: Path = COLLABORATOR_REL_DIR,
        requirements_file: Path = LITE_REQUIREMENTS_REL_PATH,
        json_creds_file: Path = CREDENTIALS_REL_PATH,
    ) -> None:
        """
        Eval specific importing command.  Able to switch between standard importing and mocked
        connection.

        Args:
            collaborator_yaml_dir: Path to collaborator agents main
                directory.
            requirements_file: Path to the requirements_file.
            json_creds_file: Path to the credentials.json file
        """
        assert json_creds_file.exists(), f"Credentials file not found. {json_creds_file}"
        assert requirements_file.exists(), f"Requirements file not found: {requirements_file}"

        # Only fetch required info if patch_env is False, and skip the actual setup of connections.
        self._setup_connections()

        if self.patch_env and self.patch_file is not None:
            eval_patch_tools_import(
                requirements_file_path=requirements_file,
                targeted_conn_id_map=self.targeted_conn_id_map,
                target_snapshot=str(self.patch_file),
            )
        elif not self.patch_env:
            multi_file_tool_import(
                requirements_file_path=requirements_file,
                targeted_conn_id_map=self.targeted_conn_id_map,
            )
        else:
            _logger.warning(f"Skipping. Expected patch file not found: {self.patch_file}")

        import_agents(
            collaborator_yaml_dir=collaborator_yaml_dir,
            domain=None,
            manager=Path(self.manager_filepath),
        )
