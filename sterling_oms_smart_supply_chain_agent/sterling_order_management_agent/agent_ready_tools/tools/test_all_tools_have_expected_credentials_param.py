from import_utils.utils.tools_data_mapper import ToolsDataList
import pytest


def test_tool_expected_credentails_param() -> None:
    """Test that all tools have defined expected_credentials."""
    compiled_tools = ToolsDataList.compile_all_tool_data()
    all_tools = compiled_tools.list_tools_data
    errors = []
    for tool in all_tools:
        if not tool.object.expected_credentials:
            errors.append(f"Tool '{tool.name}' doesn't have expected credentials defined.")

    if errors:
        pytest.fail("\n".join(errors))
