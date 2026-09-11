from pprint import pformat

from import_utils.utils.tools_data_mapper import ToolsDataList, ToolsDataMap
from import_utils.validation.validate_tools import validate_tools


def test_validate_tool_name_collisions() -> None:
    """Validation Test: Make sure there are only one to one references between tool names and
    files."""
    tools_mapper = ToolsDataMap()
    validate_tools(tools_mapper, raise_exc=True)


def test_validate_tool_to_file_mapping() -> None:
    """Validation to check if the filename mapped to tool_name actually contains the tool function
    defn."""

    tools_data_list = ToolsDataList.compile_all_tool_data()

    files_with_errors = []
    for tool_data in tools_data_list:

        with open(tool_data.file_path, "r") as fr:
            code_split = fr.read().split("@tool")
            assert len(code_split) == 2
            if tool_data.name not in code_split[1]:
                files_with_errors.append(f"{tool_data.name}: {tool_data.file_path}")

    assert (
        not files_with_errors
    ), f"Files with errors, potential mapping issues: \n{pformat(files_with_errors)}"
