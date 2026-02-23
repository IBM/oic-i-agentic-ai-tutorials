from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from ibm_watsonx_orchestrate.agent_builder.agents.agent import Agent
from import_utils.utils.logger import get_logger

# TODO: see if we want to support full Domain topological ordering.
LOGGER = get_logger(__name__)


class AgentYamlsData:
    """Class to contain all yamls either by using a Manager Agent as the entry point."""

    yaml_data: Dict[str, Any]
    manager_filepath: Path
    entrypoint_manager_name: str

    def __init__(self, *, manager_filepath: Path):
        """
        Args:
            manager_filepath: Path to the manager yaml file as an entry point.
        """
        self.manager_filepath = manager_filepath

        self.entrypoint_manager_name, self.yaml_data = self._compile_agent_yaml_data()

    def _compile_agent_yaml_data(self) -> Tuple[str, Dict[str, Any]]:
        """
        Using the filepath of the agent entrypoint, find all immediate neighboring agents and
        compile the yaml data for processing.  Requirement: Collaborators are in the same directory
        as the manager, no child subdirs.

        Returns:
            entry point agent name and all yaml data of all neighboring agents.
        """

        yml_suffixes = {".yaml", ".yml"}

        assert self.manager_filepath.exists(), f"Manager file not found: {self.manager_filepath}"

        directory = self.manager_filepath.parent
        while directory.name != "collaborator_agents":
            directory = directory.parent

        assert directory.exists(), f"Directory does not exist: '{directory}'"
        assert directory.is_dir(), f"Not a directory: '{directory}'"

        entrypoint_manager_name = None
        yaml_data: Dict[str, Any] = dict()  # Dict[AgentName, YamlData(Dict)]

        # Scan through all neighboring files (exclude subdirs)
        for root, _, files in directory.walk():
            for filename in files:
                filepath = Path(root, filename)
                if filepath.suffix in yml_suffixes:
                    agent_obj: Agent = Agent.from_spec(str(filepath))

                    yaml_data[agent_obj.name] = {
                        "collaborators": agent_obj.collaborators,
                        "tools": agent_obj.tools,
                        "filepath": str(filepath),
                    }

                    if filename == str(self.manager_filepath.name):
                        entrypoint_manager_name = agent_obj.name

        entrypoint_manager_name = (
            entrypoint_manager_name if entrypoint_manager_name is not None else "ALL"
        )
        return entrypoint_manager_name, yaml_data

    def _build_topological_order(self) -> List[str]:
        """
        Iterate through all yaml files recursively given a start directory to create an adjacency list of collaborators.
        Note: Letting cyclical dependencies fail, up to the devs to fix.

        Returns:
            list of agent yamls in safe loading order.
        """

        def recursively_build_collaborators(
            collaborators: List[str], _topological_order: List[str]
        ) -> List[str]:
            """
            Recursively scan through collaborators and build topological ordering list.

            Args:
                collaborators: list of collaborators
                _topological_order: topological ordering list

            Returns:
                List of collaborators in a specific loading order.
            """

            if not collaborators:
                return _topological_order

            r_topological_order: List[str] = list()
            process_new_nodes: List[str] = []

            for c in collaborators:
                if c not in _topological_order:
                    r_topological_order.append(c)
                    process_new_nodes.extend(self.yaml_data[c]["collaborators"])
                else:
                    LOGGER.warning(f"Cyclical Node found, Skipping: {c}")
                    continue

            n_topological_order = _topological_order + r_topological_order

            n_topological_order = recursively_build_collaborators(
                process_new_nodes, n_topological_order
            )

            return n_topological_order

        topological_order = [self.entrypoint_manager_name]
        manager_collaborators = self.yaml_data[self.entrypoint_manager_name]["collaborators"]

        topological_order = recursively_build_collaborators(
            manager_collaborators, topological_order
        )
        topological_order.reverse()

        return topological_order

    def get_topological_order_filepaths(self) -> List[str]:
        """
        Public entry point to generating topological ordering file paths.

        Returns:
            list of agent yaml file paths in topological order.
        """
        topological_keys = self._build_topological_order()
        load_order_filepaths = [
            str(self.yaml_data[agent_name]["filepath"]) for agent_name in topological_keys
        ]
        return load_order_filepaths

    def get_agent_name_to_filepath_mapping(self) -> Dict[str, str]:
        """
        Public entry point to generating a mapping of agent names to file paths.

        Returns:
            mapping of agent names to yaml file paths.
        """
        topological_keys = self._build_topological_order()
        load_order_filepaths = {
            agent_name: str(self.yaml_data[agent_name]["filepath"])
            for agent_name in topological_keys
        }
        return load_order_filepaths

    def get_tool_dependencies(self) -> Tuple[str, List[str]]:
        """
        Public entry point to generating tool dependencies based on a manager agent and its
        collaborators.

        Returns:
            manager_name for ID and group of tool dependencies tied to it.
        """
        topological_keys = self._build_topological_order()
        tools_found: Set[str] = set()
        # yaml_data contains a list of in-use collaborator agents
        for agent_name in topological_keys:
            tools_found = tools_found.union(set(self.yaml_data[agent_name]["tools"]))
        return self.entrypoint_manager_name, sorted(list(tools_found))
