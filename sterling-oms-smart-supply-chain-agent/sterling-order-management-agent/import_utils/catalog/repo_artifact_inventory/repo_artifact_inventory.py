from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

from import_utils.connections.tools_app_id_mapper import ConnectionsToolMapper
from import_utils.tool_importer.agent_yamls_data import AgentYamlsData
from import_utils.utils.directory import find_target_directory
from rich.progress import track
from utils.directory.path_validators import is_valid_dir_path


@dataclass(frozen=True)
class RepoArtifactInventory:
    """Container for an inventory of all managers, agents, tools, and app-ids configured in our
    repo."""

    all_managers: List[str] = field(default_factory=list)
    all_agents: List[str] = field(default_factory=list)
    all_tools: List[str] = field(default_factory=list)
    all_app_ids: List[str] = field(default_factory=list)

    excluded_managers: List[str] = field(default_factory=list)


def build_repo_artifact_inventory(
    only_managers: Optional[List[str]] = None,
    agent_yamls_dir: Optional[Path] = None,
) -> RepoArtifactInventory:
    """
    Build a RepoArtifactInventory object containing a list of all managers, agents, tools, and app-
    ids configured in our repo.

    Args:
        only_managers: if specified, only these managers, along with their collaborators,
            tools and app-ids will be included.
        agent_yamls_dir: optional, the directory for the agent yaml files to use for creating
            inventory of repo artifacts.

    Returns:
        An object containing a list of all managers, agents, tools, and app-ids currently
        configured in our repo.
    """

    all_managers: Set[str] = set()
    all_agents: Set[str] = set()
    all_tools: Set[str] = set()
    all_app_ids: Set[str] = set()

    excluded_managers: Set[str] = set()

    # TODO: pass the list of manager filepaths as entry point to this function to allow for easier testing
    # and remove logic below.

    if agent_yamls_dir:
        source_dir = Path(__file__).parent.parent.parent
        collaborator_dir = source_dir / agent_yamls_dir
        collaborator_dir = collaborator_dir.relative_to(source_dir)
        assert is_valid_dir_path(collaborator_dir)
    else:
        collaborator_dir = find_target_directory("collaborator_agents")
        assert collaborator_dir.exists()
    manager_filepaths = list(collaborator_dir.rglob("*manager.yaml"))
    connections_tool_mapper = ConnectionsToolMapper()

    for filepath in track(
        manager_filepaths, description="Generating repo artifacts inventory from agent yamls..."
    ):
        manager_yaml_data = AgentYamlsData(manager_filepath=filepath)
        manager_name = manager_yaml_data.entrypoint_manager_name

        if only_managers and manager_name not in only_managers:
            excluded_managers |= set([manager_name])
            continue

        agents = manager_yaml_data.get_agent_name_to_filepath_mapping()
        tools = manager_yaml_data.get_tool_dependencies()[1]

        all_managers |= set([manager_name])
        all_agents |= set(agents)
        all_tools |= set(tools)

        for tool in tools:
            connections = connections_tool_mapper.get_required_connections_for_tool_list([tool])
            assert connections, f"Tool {tool!r} is missing 'expected_credentials' param."
            all_app_ids |= set(connections)

    if only_managers:
        assert not (
            non_existent_managers := set(only_managers) - all_managers
        ), f"Managers: {non_existent_managers} do not exist in repo"

    return RepoArtifactInventory(
        all_managers=sorted(all_managers),
        all_agents=sorted(all_agents),
        all_tools=sorted(all_tools),
        all_app_ids=sorted(all_app_ids),
        excluded_managers=sorted(excluded_managers),
    )
