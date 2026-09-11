from import_utils.utils.tools_data_mapper import ToolsDataList
import pytest

from agent_ready_tools.utils.tool_docstring import validate_google_style_docstring


def test_tool_argument_descriptions() -> None:
    """Test that all tool arguments have non-empty docstring descriptons."""
    compiled_tools = ToolsDataList.compile_all_tool_data()
    all_tools = compiled_tools.list_tools_data
    errors = []
    for tool in all_tools:
        validation_result = validate_google_style_docstring(tool.object)
        if not validation_result.is_valid:
            if validation_result.docstring_missing:
                msg = (
                    f"Tool `{tool.name}`: Docstring is missing. "
                    f"Arguments with errors: {validation_result.arguments_with_errors or 'None'} "
                    f"{validation_result.return_error or ''}"
                )
            else:
                msg = (
                    f"Tool `{tool.name}` has invalid docstring. "
                    f"Arguments with errors: {validation_result.arguments_with_errors or 'None'} "
                    f"{validation_result.return_error or ''}"
                )
            errors.append(msg)

    if errors:
        pytest.fail("\n\n".join(errors))
