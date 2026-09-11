import multiprocessing
import os
from pathlib import Path
import shutil
from typing import Dict, List, Mapping, Optional, Tuple

from ibm_watsonx_orchestrate.cli.commands.tools.tools_command import tool_import
from ibm_watsonx_orchestrate.cli.commands.tools.tools_controller import ToolKind
from ibm_watsonx_orchestrate.client.utils import is_local_dev
from import_utils.utils.directory import find_target_directory
from import_utils.utils.tools_data_mapper import ToolData, ToolsDataMap
from import_utils.validation.dependency_mapper import (
    build_dependency_init_manifest,
    primitive_dependency_mapping,
)

from agent_ready_tools.utils.env import is_running_export_catalog
from agent_ready_tools.utils.tool_credentials import IBM_PUBLISHER_SUFFIX


def _inject_tools_syspath(modify_file_path: Path) -> None:
    """
    Add code to tool files for it to work properly in the chat client. Tool code is uploaded to the
    server side by way of zip.  Modules will not be initialized until chat runtime. Injected code
    adds the `agent_ready_tools` directory that is packaged in the zip to the sys.path. This gives
    python a place to look when importing module dependencies from the tool code.

    Pending new TRM architecture. Estimated release End of May 2025.
    https://github.ibm.com/WatsonOrchestrate/wo-tracker/issues/31903
    TODO: remove this function when TRM update has been released.

    Args:
        modify_file_path: Path to the modified file.
    """

    injectable_py_code = """
from pathlib import Path
import sys

test_dir = Path(__file__).parent
BASE_DIR = 'agent_ready_tools'
MAX_DEPTH = 10

while test_dir.name != BASE_DIR:
    test_dir = test_dir.parent
    MAX_DEPTH -= 1
    if MAX_DEPTH == 0:
        raise RecursionError(f"'{BASE_DIR}' not found in path: {__file__}")
parent_path = test_dir.parent.resolve()

sys.path.append(str(parent_path))
    """

    py_reader = open(modify_file_path, "r")
    tool_code = py_reader.read()
    py_reader.close()

    py_writer = open(modify_file_path, "w")
    py_writer.write(injectable_py_code + "\n" + tool_code)
    py_writer.close()


def build_client_specific_deliverables(
    targeted_tools_data_map: Dict[str, ToolData],
    tmp_dir_name: str = "multifile_imports",
) -> Tuple[Mapping[str, Path], Path]:
    """
    Build the temporary workspace for v1.0.0+ tool code for packaging and loading. Use the
    dependency mapper to build a copy of `agent_ready_tools` but only containing the required files
    for all tools listed in the targeted agent yaml and its collaborators.

    v1.0.0+ multi-file import packaging involves a target_tool_py_filepath and a package_root_filepath.
    There is a check to verify target_tool_py_filepath is a child path of package_root_filepath.
    Then everything in package_root_filepath is zipped up and loaded to the server.

    Building a temporary workspace will allow us to limit the scope of what will be loaded into orchestrate
    without affecting our main repo.

    Args:
        targeted_tools_data_map: Mapping from tool name to ToolsData object.
        tmp_dir_name: Temporary working directory name

    Returns:
        Map of tool name to modified tool file and local tmp working directory.
    """

    tool_name_to_temp_tool_filepath = {}
    local_import_utils_dir = find_target_directory("import_utils")
    local_workspace_dir = local_import_utils_dir / "tmp_export_tools" / tmp_dir_name

    package_root = find_target_directory("agent_ready_tools")

    # Set of Tuples: (pants abs path, rel path)
    manager_dep_manifest = set()
    all_dep_manifests = []
    for tool_name, tool_obj in targeted_tools_data_map.items():
        tool_file_path = tool_obj.file_path
        tmp_tool_filepath = local_workspace_dir / (tool_file_path.relative_to(package_root.parent))
        tool_name_to_temp_tool_filepath[tool_name] = tmp_tool_filepath

        manager_dep_manifest.add((tool_file_path, tmp_tool_filepath))

        dep_manifest = primitive_dependency_mapping(package_root, tool_file_path)
        for pants_abs_path, rel_path in dep_manifest:
            tmp_abs_path = local_workspace_dir / rel_path
            manager_dep_manifest.add((pants_abs_path, tmp_abs_path))

        all_dep_manifests.append(dep_manifest)

    # Create intermediate subdirs and copy tool file into end of dir structure
    for pants_abs_path, tmp_abs_path in manager_dep_manifest:
        os.makedirs(str(tmp_abs_path.parent), exist_ok=True)
        shutil.copy(str(pants_abs_path), str(tmp_abs_path))

    # Compatibility modifications to the deliverables.
    for tmp_tool_filepath in tool_name_to_temp_tool_filepath.values():
        # TODO: remove once TRM issue has been resolved, see function docstring for details.
        _inject_tools_syspath(tmp_tool_filepath)

    if is_local_dev() and not is_running_export_catalog():
        tool_creds_path = (
            local_workspace_dir / "agent_ready_tools" / "utils" / "tool_credentials.py"
        )
        assert tool_creds_path.exists() and tool_creds_path.is_file()
        tool_creds_path.write_text(tool_creds_path.read_text().replace(IBM_PUBLISHER_SUFFIX, ""))

    # Build a new init manifest, then create inits for python module importing
    init_manifest = build_dependency_init_manifest(
        package_root,
        list(manager_dep_manifest),
    )
    for init_rel_path, _ in init_manifest:
        tmp_abs_path = local_workspace_dir / init_rel_path
        tmp_abs_path.touch(exist_ok=True)

    return tool_name_to_temp_tool_filepath, local_workspace_dir


def multi_file_tool_import(
    requirements_file_path: Path,
    targeted_conn_id_map: Dict[str, Optional[List[str]]],
) -> None:
    """
    If manager_id is defined, targeted_tools list can be retrieved. This block of code uses
    multiprocessing to import the tools in targeted_tools concurrently.

    Args:
        requirements_file_path: The path to the requirements_file.
        targeted_conn_id_map: Map of all tools for a specific manager and its required connections
            ids.
    """

    tools_data_map = ToolsDataMap().get_tool_name_to_tool_data_map()

    filtered_tools_data_map = {
        tool_name: tools_data
        for tool_name, tools_data in tools_data_map.items()
        if tool_name in targeted_conn_id_map
    }
    tool_name_to_temp_tool_filepath, local_workspace_dir = build_client_specific_deliverables(
        filtered_tools_data_map
    )

    multithreaded_args = [
        (
            ToolKind.python,
            str(tool_name_to_temp_tool_filepath[tool_name]),
            tool_app_ids,
            str(requirements_file_path),
            str(local_workspace_dir),
        )
        for tool_name, tool_app_ids in targeted_conn_id_map.items()
    ]

    with multiprocessing.Pool(processes=max(multiprocessing.cpu_count() // 2, 1)) as pool:
        pool.starmap(tool_import, multithreaded_args)
