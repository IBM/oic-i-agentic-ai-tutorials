from unittest.mock import MagicMock, patch

from import_utils.catalog.config_data_test import (
    TEST_COLLABORATOR_DIRPATH,
    mock_get_required_connections_for_tool_list,
    mock_get_tool_by_name,
)
from import_utils.catalog.repo_artifact_inventory.repo_artifact_inventory import (
    RepoArtifactInventory,
    build_repo_artifact_inventory,
)

TEST_REPO_ARTIFACT_ALL_MANAGERS = RepoArtifactInventory(
    all_managers=["test_1_manager", "test_2_manager"],
    all_agents=[
        "test_1_collaborator_agent",
        "test_1_manager",
        "test_2_collaborator_agent",
        "test_2_manager",
    ],
    all_tools=["test_tool_1", "test_tool_2"],
    all_app_ids=["test_app_id_1", "test_app_id_2"],
    excluded_managers=[],
)

TEST_REPO_ARTIFACT_ONLY_MANAGERS = RepoArtifactInventory(
    all_managers=["test_2_manager"],
    all_agents=["test_2_collaborator_agent", "test_2_manager"],
    all_tools=["test_tool_1"],
    all_app_ids=["test_app_id_1", "test_app_id_2"],
    excluded_managers=["test_1_manager"],
)


@patch(
    "import_utils.connections.tools_app_id_mapper.ConnectionsToolMapper.get_required_connections_for_tool_list"
)
@patch("import_utils.utils.tools_data_mapper.ToolsDataMap.get_tool_by_name")
def test_build_repo_artifact_inventory_all_managers(
    mock_tool_method: MagicMock, mock_connections_method: MagicMock
) -> None:
    """Test repo artifact inventory for all manager agents."""
    mock_tool_method.side_effect = mock_get_tool_by_name
    mock_connections_method.side_effect = mock_get_required_connections_for_tool_list

    artifact_inventory: RepoArtifactInventory = build_repo_artifact_inventory(
        agent_yamls_dir=TEST_COLLABORATOR_DIRPATH
    )

    assert artifact_inventory == TEST_REPO_ARTIFACT_ALL_MANAGERS


@patch(
    "import_utils.connections.tools_app_id_mapper.ConnectionsToolMapper.get_required_connections_for_tool_list"
)
@patch("import_utils.utils.tools_data_mapper.ToolsDataMap.get_tool_by_name")
def test_build_repo_artifact_inventory_only_managers(
    mock_tool_method: MagicMock, mock_connections_method: MagicMock
) -> None:
    """Test repo artifact inventory with a subset of managers, specified via only_managers param."""
    mock_tool_method.side_effect = mock_get_tool_by_name
    mock_connections_method.side_effect = mock_get_required_connections_for_tool_list

    artifact_inventory: RepoArtifactInventory = build_repo_artifact_inventory(
        only_managers=["test_2_manager"], agent_yamls_dir=TEST_COLLABORATOR_DIRPATH
    )

    assert artifact_inventory == TEST_REPO_ARTIFACT_ONLY_MANAGERS
