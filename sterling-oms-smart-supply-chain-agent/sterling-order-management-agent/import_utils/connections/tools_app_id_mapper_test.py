from pathlib import Path
from unittest.mock import patch

from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType, ExpectedCredentials
from ibm_watsonx_orchestrate.agent_builder.tools.python_tool import PythonTool
from import_utils.connections.tools_app_id_mapper import ConnectionsToolMapper
import import_utils.utils.tools_data_mapper
from import_utils.utils.tools_data_mapper import ToolData
import pytest

from agent_ready_tools.utils.tool_credentials import published_app_id


# Position before patcher so it can properly build tools map
def test_sanity_check_on_real_tool() -> None:
    """
    Test to see if we can fetch a connections data on a real tool.

    SAP requires app-ids.
    """
    sap_tools = ["get_benefits_plan"]

    actual_conns = ConnectionsToolMapper().get_required_connections_for_tool_list(sap_tools)
    assert set(actual_conns) == {
        published_app_id("sap_successfactors_basic"),
        published_app_id("sap_successfactors_key_value"),
    }


def _build_tool_data(file_path: Path, tool_obj: PythonTool) -> ToolData:
    """
    Builder for ToolData, easier to manage.

    Args:
        file_path: test file path
        tool_obj: test PythonTool

    Returns:
        ToolData
    """
    return ToolData(
        name=str(file_path).replace("/", "_"),
        object=tool_obj,
        file_path=file_path,
        module_name=str(file_path).replace("/", "."),
    )


TEST_DATA_TOOLS = {
    "test_tool1": _build_tool_data(
        file_path=Path("test/tool1.py"),
        tool_obj=PythonTool(
            fn=None,
            spec=None,
            expected_credentials=[
                ExpectedCredentials(app_id="test_conn1.1", type=ConnectionType.BASIC_AUTH),
                ExpectedCredentials(app_id="test_conn1.2", type=ConnectionType.BASIC_AUTH),
            ],
        ),
    ),
    "test_tool2": _build_tool_data(
        file_path=Path("test/tool2.py"),
        tool_obj=PythonTool(
            fn=None,
            spec=None,
            expected_credentials=[
                ExpectedCredentials(app_id="test_conn2.1", type=ConnectionType.BASIC_AUTH),
                ExpectedCredentials(app_id="test_conn2.2", type=ConnectionType.BASIC_AUTH),
            ],
        ),
    ),
    "test_tool3": _build_tool_data(
        file_path=Path("test/tool3.py"),
        tool_obj=PythonTool(fn=None, spec=None, expected_credentials=[]),
    ),
    "test_tool4": _build_tool_data(
        file_path=Path("test/tool4.py"), tool_obj=PythonTool(fn=None, spec=None)
    ),
}
TEST_DATA_APPIDS = {
    "test_tool1": {"test_conn1.1", "test_conn1.2"},
    "test_tool2": {"test_conn2.1", "test_conn2.2"},
}


@pytest.fixture(scope="module", name="conns_mapper")
def fixture_build_patched_conns_mapper() -> ConnectionsToolMapper:
    """Fixture to patch in test data."""
    with patch.object(
        import_utils.utils.tools_data_mapper.ToolsDataMap,
        "get_tool_name_to_tool_data_map",
        return_value=TEST_DATA_TOOLS,
    ):
        return ConnectionsToolMapper()


def test_get_tools_expected_connections(conns_mapper: ConnectionsToolMapper) -> None:
    """
    Test the construction of the map by checking through the tool_name -> PythonTool object map.

    The map is supplied by a different module. Expected behavior: ConnectionsToolMapper will only
    contain the information for PythonTools that have `expected_credentials`.
    """
    assert conns_mapper.tool_name_to_app_id_map == TEST_DATA_APPIDS

    assert "test_tool3" not in conns_mapper.tool_name_to_app_id_map
    assert "test_tool4" not in conns_mapper.tool_name_to_app_id_map


def test_get_required_connections_for_an_individual_tool(
    conns_mapper: ConnectionsToolMapper,
) -> None:
    """
    Test the fetching of a specific tool.

    You can access the class attribute directly and fetch the data for single tools. Preferred to
    use .get() to fetch so it doesn't throw a KeyError for nonexistent tools.
    """
    expected_conns = TEST_DATA_APPIDS["test_tool2"]
    assert conns_mapper.tool_name_to_app_id_map.get("test_tool2") == expected_conns


def test_get_required_connections_for_tool_list(conns_mapper: ConnectionsToolMapper) -> None:
    """
    Test the fetching of certain set of tools from the map.

    Even though the Mapper has info on all tools and their expected_credentials info, we should be
    able to pass in a list of tool_names and provide a set of app_ids to bind to the tool.
    """
    expected_conns = TEST_DATA_APPIDS["test_tool2"]
    actual_conns = conns_mapper.get_required_connections_for_tool_list(["test_tool2"])
    assert set(actual_conns) == expected_conns


def test_get_tool_conns_with_no_app_ids(conns_mapper: ConnectionsToolMapper) -> None:
    """Test fetching of tools that don't have `expected_credentials`."""
    assert conns_mapper.get_required_connections_for_tool_list(["test_tool3"]) == []
    assert conns_mapper.tool_name_to_app_id_map.get("test_tool3") is None


def test_get_tool_conns_mix_of_avail_and_nonexistent_conns(
    conns_mapper: ConnectionsToolMapper,
) -> None:
    """
    Test fetching of tools that have and don't have `expected_credentials`.

    If the tools do not exist in the map, then it will return an empty set of app_ids. But if a tool
    in the list does have connections, it will still compile app_ids.
    """
    actual_conns = conns_mapper.get_required_connections_for_tool_list(["test_tool2", "test_tool3"])
    assert set(actual_conns) == TEST_DATA_APPIDS["test_tool2"]
