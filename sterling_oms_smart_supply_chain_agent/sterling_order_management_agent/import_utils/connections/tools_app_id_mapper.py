"""Find tools objects, then map to an app_id if available."""

from pathlib import Path
from typing import List, Mapping, Optional, Set

from import_utils.utils.tools_data_mapper import ToolData, ToolsDataMap


class ConnectionsToolMapper:
    """Build mapping of all available tools to app_ids."""

    tool_name_to_app_id_map: Mapping[str, Set[str]]
    "Mapping of tool names to app ids"

    def __init__(self, agent_ready_tools_parent: Optional[Path] = None):
        """
        Args:
            agent_ready_tools_parent: custom tools path if needed
        """
        tools_data_map = ToolsDataMap().get_tool_name_to_tool_data_map()
        self.tool_name_to_app_id_map = self._get_tools_expected_connections(tools_data_map)

    def _get_tools_expected_connections(
        self, tools_data_map: Mapping[str, ToolData]
    ) -> Mapping[str, Set[str]]:
        """
        Find all tool objects and extract the expected connections for each tool.

        Args:
            tools_data_map: mapping of tool names to PythonTool objects

        Returns:
            mapping from tool name to list of connections.
        """
        _tool_name_to_app_id_map = dict()
        for tool_name, tool_data in tools_data_map.items():
            if tool_data.object.expected_credentials:
                _tool_name_to_app_id_map[tool_name] = {
                    c.app_id for c in tool_data.object.expected_credentials
                }

        return _tool_name_to_app_id_map

    def get_required_connections_for_tool_list(self, tool_name_list: List[str]) -> List[str]:
        """
        Use mapping and determine which connections are required for a group of tools.

        Args:
            tool_name_list: list of tool names.

        Returns:
            list of connections.
        """
        _required_app_ids: Set[str] = set()
        for _tool_name in tool_name_list:
            _required_app_ids.update(i for i in self.tool_name_to_app_id_map.get(_tool_name, []))
        return list(_required_app_ids)
