from collections import defaultdict
from dataclasses import dataclass
from importlib import import_module
import inspect
import os
from pathlib import Path
from typing import Dict, Iterator, List, Mapping, Optional

from ibm_watsonx_orchestrate.agent_builder.tools import PythonTool
from import_utils.utils.directory import find_target_directory


@dataclass
class ToolData:
    """Container for data from tools searching."""

    name: str
    object: PythonTool
    file_path: Path
    module_name: str


class ToolsDataList:
    """List of all tools and tool data, duplicate references as well."""

    list_tools_data: List[ToolData]

    def __init__(self, tools_data: List[ToolData]) -> None:
        """
        Args:
            tools_data: list of tools data
        """
        self.list_tools_data = tools_data

    # TODO: Use this for the tool name validation after we move validation into import_utils
    @classmethod
    def compile_all_tool_data(
        cls,
        agent_ready_tools_parent: Optional[Path] = None,
    ) -> "ToolsDataList":
        """
        Scan the agent_ready_tools/tools dir for any PythonTool object. Compile a list of all
        available tool files and relevant data.

        Args:
            agent_ready_tools_parent: parent directory of agent_ready_tools dir

        Returns:
            reference of all available tools, can be used to validate or map agents to tools.
        """

        if agent_ready_tools_parent is None:
            agent_ready_tools_parent = find_target_directory("agent_ready_tools")

        list_all_tools_data = []
        for root, _, files in agent_ready_tools_parent.walk():
            for file in files:
                if Path(file).suffix != ".py":
                    continue
                if file == "__init__.py":
                    continue
                module_path = Path(root) / file
                assert module_path.exists()

                # From file path, build an importable string.
                module_rel_path = module_path.relative_to(agent_ready_tools_parent.parent)
                module_name, _ = os.path.splitext(str(module_rel_path).replace("/", "."))

                # Need to import the module so we can analyze the contents.
                module = import_module(module_name)

                # {module_name} should look like what we as devs import in the top of a python file.
                #   agent_ready_tools.tools.procurement.purchase_support.coupa.get_approvals_by_req_id
                # The tool spec binding function will have an import from the scope of pants run
                #   .private.var.folders.hw.0vxhn6193t77hnfkt3w8_1hm0000gn.T.pants-sandbox-tGQTKx...{module_name}
                # So we can just check to see if {module_name} is a substring of the tool spec binding.
                #   Doing so will identify the object as a local member and not imported in from a different location.
                for name, obj in inspect.getmembers(module):
                    if isinstance(obj, PythonTool):  # Function has been decorated with @tool
                        tdata = ToolData(
                            name=str(name),
                            object=obj,
                            file_path=module_path,
                            module_name=module_name,
                        )
                        list_all_tools_data.append(tdata)

        return cls(list_all_tools_data)

    def __iter__(self) -> Iterator[ToolData]:
        """
        Iter impl to allow for use in `for` loops.

        Returns:
            iterator of internal tools data list
        """
        for tool_data in self.list_tools_data:
            yield tool_data


class ToolsDataMap:
    """Gather all python tool objects and make them referencable."""

    _tools_map: Dict[str, ToolData]
    "Main tool map of only valid tools."
    invalid_tools: Dict[str, List[ToolData]]
    "Invalid tools that have too many references."

    def __init__(self, agent_ready_tools_parent: Optional[Path] = None) -> None:
        """
        Args:
            agent_ready_tools_parent: parent directory of agent_ready_tools dir
        """
        self._tools_map = dict()
        self.invalid_tools = defaultdict(list)

        tools_data_list = ToolsDataList.compile_all_tool_data(agent_ready_tools_parent)
        self._build_tool_data_map(tools_data_list)

    def _build_tool_data_map(self, tools_data_list: ToolsDataList) -> None:
        """
        Scan the agent_ready_tools/tools dir for any PythonTool object. Compile a list of modules
        that have a function keyed to the tool function name.

        Args:
            tools_data_list: list of tools data

        Returns:
            reference of all available tools, can be used to validate or map agents to tools.
        """
        for tool_data in tools_data_list:

            # Some reason the _list_tools_data contains duplicate valid entries.
            if tool_data.name in self._tools_map and tool_data == self._tools_map[tool_data.name]:
                continue

            # Filter out any tool_names with multiple file references into a separate mapping.
            if tool_data.name not in self._tools_map:
                self._tools_map[tool_data.name] = tool_data
            else:
                if tool_data.name not in self.invalid_tools:
                    self.invalid_tools[tool_data.name].append(self._tools_map[tool_data.name])
                self.invalid_tools[tool_data.name].append(tool_data)

        for remove_key in self.invalid_tools.keys():
            self._tools_map.pop(remove_key, None)

    def get_tool_name_to_tool_data_map(self) -> Mapping[str, ToolData]:
        """
        Public accessor for _tools_map. Return as immutable mapping.

        Returns:
            reference of all available tools, can be used to validate or map agents to tools.
        """
        return self._tools_map

    def get_tool_by_name(self, tool_name: str) -> Optional[ToolData]:
        """
        Public Getter for tool data by name.

        Args:
            tool_name: tool name to search for

        Returns:
            tool data if found, else None
        """
        return self._tools_map.get(tool_name, None)
