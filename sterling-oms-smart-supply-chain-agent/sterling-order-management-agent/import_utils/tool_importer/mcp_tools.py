import json
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Set, Union

from ibm_watsonx_orchestrate.cli.commands.toolkit.toolkit_command import (
    import_toolkit,
    remove_toolkit,
)
from ibm_watsonx_orchestrate.cli.commands.toolkit.toolkit_controller import ToolkitKind
from import_utils.connections.import_connections import ConnectionManager
from import_utils.utils.logger import get_logger
import yaml

from agent_ready_tools.utils.tool_credentials import published_app_id

LOGGER = get_logger(__name__)


# TODO: use a schema dataclass? instead of just a json
def _parse_package_json(json_path: Path) -> Dict[str, Union[str, List[str]]]:
    """Read the package.json for a toolkit and parse specific data out of it."""
    json_data = json.load(open(json_path, "r"))
    return {
        "name": json_data["name"],
        "description": json_data["description"],
        "command": json_data["scripts"]["start"],
        "app_ids": json_data["app_ids"],
    }


def mcp_tools_import(package_root: Path, mcp_yaml: Optional[Path] = None) -> None:
    """
    Specific importer for JS MCP toolkits.

    # TODO: introduce a new --mcp argument in `import_command`, this will be used instead of --manager
    # TODO: find relative paths so we can build dist in pants and toss after we are done, instead of adding to tmp.

    Args:
        package_root: Path to the root of the package.
        mcp_yaml: Path to the mcp.
    """
    assert package_root.exists(), f"Package root doesn't exist: {package_root}"
    assert package_root.is_dir(), f"Package root is not a directory: {package_root}"

    package_json_path = package_root / "package.json"

    assert (
        package_json_path.exists()
    ), f"package.json not found in package root: {package_json_path}"
    json_data = _parse_package_json(package_json_path)

    if mcp_yaml is not None:
        assert mcp_yaml.name.endswith(
            "_mcp.yaml"
        ), f"Please verify manager yaml is compatible with MCP: {mcp_yaml} (Filename should end with `_mcp.yaml`)"

        yml_data = yaml.safe_load(open(mcp_yaml, "r"))
        yaml_tools = ", ".join(yml_data["tools"])
        assert all(
            json_data["name"] in tool_name for tool_name in yml_data["tools"]
        ), f"Please verify toolkit identifier is in the MCP yaml tool definitions. Toolkit name: '{json_data["name"]}' Yaml Tools: '{yaml_tools}'"

    # There is no toolkit update logic, so we will need to clear existing tools before reimporting.
    LOGGER.info(f"Attempting to remove toolkit {json_data["name"]} if it exists.")
    remove_toolkit(json_data["name"])

    json_data["app_ids"] = list(map(lambda item: published_app_id(item), json_data["app_ids"]))

    # Build Connections
    ConnectionManager().import_connections(tuple(json_data["app_ids"]))

    # TODO: pull list from yaml if we want to have fine tuned control
    tools = None
    # toolkits will have multiple tools defined in JS. But sometimes user wants to only import certain ones from JS code.

    import_toolkit(
        kind=ToolkitKind.MCP,
        name=json_data["name"],
        description=json_data["description"],
        package_root=str(package_root),
        command=json_data["command"],
        tools=tools,
        app_id=json_data["app_ids"],
    )


def get_toolkits_mapping(map_dir_path: Path) -> Mapping[str, Path]:
    """
    Scan path for all package.json files and build mapping.

    Args:
        map_dir_path: Path to the mcp yaml.

    Returns:
        Mapping from toolkit name to toolkit package path.
    """

    toolkit_name_to_pkg_root_map = dict()
    for root, _, files in map_dir_path.walk():
        for file in files:
            if file == "package.json":
                if "node_modules" in str(root):
                    continue

                package_path = root / file
                json_data = json.load(open(str(package_path), "r"))

                if "name" in json_data:
                    toolkit_name = json_data["name"]
                    toolkit_name_to_pkg_root_map[toolkit_name] = root

    return toolkit_name_to_pkg_root_map


def extract_toolkits(yaml_path: Path) -> Set[str]:
    """
    Scan yaml for any toolkits.

    Args:
        yaml_path: Path to the mcp manager yaml

    Returns:
        Set of toolkits
    """
    toolkits_set = set()
    yaml_data = yaml.load(open(str(yaml_path), "r"), Loader=yaml.SafeLoader)

    for collaborator in yaml_data["collaborators"]:
        collab_path = yaml_path.parent / (collaborator + ".yaml")
        assert collab_path.exists()
        collab_tools = extract_toolkits(collab_path)
        toolkits_set.update(collab_tools)

    for tool in yaml_data["tools"]:
        if ":" in tool:
            toolkits_set.add(tool.split(":")[0])

    return toolkits_set
