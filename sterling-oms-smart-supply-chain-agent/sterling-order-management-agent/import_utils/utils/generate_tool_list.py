from collections import defaultdict
import os
from typing import Any, Dict, List

from import_utils.utils.tools_data_mapper import ToolsDataList

_TOOL_LIST_FILE = "tool_list.md"
_TABLE_HEADER = "| Tool Name | Tool Description |\n|---|---|"


def snake_case_to_title_case(snake_case_str: str) -> str:
    """
    Converts the provided string from snake case to title case.

    Args:
        snake_case_str: A snake case string.

    Returns:
        A title case string.
    """
    return snake_case_str.replace("_", " ").title()


def _append_tool_group_info(
    markdown_content: List[str], systems: Dict[str, List[Any]]
) -> List[str]:
    """
    Writes a given domain/use case's tool info by system to markdown_content.

    Args:
        markdown_content: The existing state of the _TOOL_LIST_FILE.
        systems: The tools in this domain/use case keyed by the system they interact with.

    Returns:
        The markdown_content with the domain/use case's tool info appended.
    """
    for system in sorted(list(systems.keys())):
        tools = systems[system]
        markdown_content.append(f"#### {snake_case_to_title_case(system)}")
        markdown_content.append(_TABLE_HEADER)

        for tool in sorted(tools, key=lambda t: t.__tool_spec__.name):
            # Pull data from Python docstring formatted using Google Docstring.
            tool_desc = tool.__tool_spec__.description.rstrip().split("\n\n")[0].replace("\n", " ")
            markdown_content.append(f"| `{tool.__tool_spec__.name}` | {tool_desc} |")
    return markdown_content


def main() -> None:
    """Writes all registered tools to _TOOL_LIST_FILE."""
    tools_data_list = sorted(
        ToolsDataList.compile_all_tool_data().list_tools_data, key=lambda td: td.name
    )
    tools = [t.object for t in tools_data_list]

    tool_groups_with_use_case: Dict[str, Dict[str, Dict[str, List[Any]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    tool_groups_without_use_case: Dict[str, Dict[str, List[Any]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for tool in tools:
        tool_path = tool.fn.__code__.co_filename
        path_components = tool_path.split(os.sep)

        # We expect one of the following structures:
        # .../tools/<domain>/<system>/tool_file.py
        # .../tools/<domain>/<use case>/<system>/tool_file.py
        tools_index = path_components.index("tools")
        domain = path_components[tools_index + 1]
        if len(path_components) > tools_index + 4:
            # has 'use_case'
            use_case = path_components[tools_index + 2]
            system = path_components[tools_index + 3]
            tool_groups_with_use_case[domain][use_case][system].append(tool)
        else:
            system = path_components[tools_index + 2]
            tool_groups_without_use_case[domain][system].append(tool)

    markdown_content: List[str] = ["# Tools"]
    for domain in sorted(list(tool_groups_with_use_case.keys())):

        use_cases = tool_groups_with_use_case[domain]
        markdown_content.append(f"## {snake_case_to_title_case(domain)}")
        for use_case in sorted(list(use_cases.keys())):
            systems = use_cases[use_case]
            markdown_content.append(f"### {snake_case_to_title_case(use_case)}")
            markdown_content = _append_tool_group_info(markdown_content, systems)

    for domain in sorted(list(tool_groups_without_use_case.keys())):
        systems = tool_groups_without_use_case[domain]
        markdown_content.append(f"## {snake_case_to_title_case(domain)}")
        markdown_content = _append_tool_group_info(markdown_content, systems)

    with open(_TOOL_LIST_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(markdown_content))


if __name__ == "__main__":
    main()
