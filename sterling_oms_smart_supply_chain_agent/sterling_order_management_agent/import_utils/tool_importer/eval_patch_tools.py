"""
For Evaluations using the patching method for mocking Tool Responses.

TODO: Migrate ADK Validation CI/CD to patching method and replace eval_tools.py with this one.
"""

import ast
import dataclasses
import multiprocessing
from pathlib import Path
import shutil
from typing import Optional

from ibm_watsonx_orchestrate.cli.commands.tools.tools_command import tool_import
from ibm_watsonx_orchestrate.cli.commands.tools.tools_controller import ToolKind
from import_utils.tool_importer.multifile_tools import build_client_specific_deliverables
from import_utils.utils.directory import find_target_directory
from import_utils.utils.logger import get_logger
from import_utils.utils.tools_data_mapper import ToolsDataMap

from agent_ready_tools.utils.tool_snapshot.patch import PatchMode

_logger = get_logger(__name__)

SNAPSHOT_UTILS_DEFAULT_DIR = "agent_ready_tools/utils/tool_snapshot"
# Although broad, no risk if multiple patching occurs.
INJECTABLE = """
# ---- EVAL PATCH START ---- #
from agent_ready_tools.utils.tool_snapshot.patch import patch_python_tool_call_func, patch_expected_credentials
patcher = patch_python_tool_call_func("{patch_data_filepath}")
patcher.__enter__()
conn_patcher = patch_expected_credentials()
conn_patcher.__enter__()
# ---- EVAL PATCH END ---- #
"""


@dataclasses.dataclass
class PatchConfig:
    """
    PatchConfig dataclass containing data needed for enabling replay.

    Setup code for configuration based importing.
    """

    patch_mode: PatchMode
    patch_data_filepath: str


DEFAULT_PATCH_CONFIG = PatchConfig(
    patch_mode=PatchMode.REPLAY,
    patch_data_filepath="agent_ready_tools/utils/tool_snapshot/patch_data.py",
)


def _find_decorator_line(code: str, decorator_id: str) -> Optional[int]:
    """
    Find the line number of the first @tool decorator in Python code.

    Args:
        code: Python source code as string
        decorator_id: id of the decorator to find

    Returns:
        Line number (1-indexed) of first @tool decorator, or None if not found
    """

    def _from_decorator_to_line(func_def: ast.FunctionDef, _decorator_id: str) -> Optional[int]:
        """
        Helper function for finding the line number of the first @tool decorator in Python code.

        Used to prevent `R1702(too-many-nested-blocks)` pylint failure.

        Args:
            func_def: AST function definition
            _decorator_id: id of the decorator to find

        Returns:
            Line number (1-indexed) of first @tool decorator, or None if not found
        """

        for decorator in func_def.decorator_list:
            # Check @tool (without parentheses)
            if isinstance(decorator, ast.Name) and decorator.id == _decorator_id:
                return decorator.lineno
            # Check @tool() (with parentheses)
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name) and decorator.func.id == _decorator_id:
                    return decorator.lineno
        return None

    try:
        tree = ast.parse(code)
    except SyntaxError:
        _logger.warning(f"Could not parse code, skipping")
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            deco_lineno = _from_decorator_to_line(node, decorator_id)
            if deco_lineno is not None:
                return deco_lineno

    return None


def _inject_code_before_line(code: str, injectable: str, line_number: int) -> str:
    """
    Insert code before a specific line number.

    Args:
        code: Original source code
        injectable: Code to inject
        line_number: Line number (1-indexed) to insert before

    Returns:
        Modified code with injection
    """
    lines = code.splitlines(keepends=True)
    lines.insert(line_number - 1, injectable + "\n")
    return "".join(lines)


def inject_tool_patching(tmp_workspace_dir: Path, patch_cfg: PatchConfig) -> None:
    """
    Injects code into Python tool files to enable patching.

    Add a patching snippet to all Python files decorated with `@tool`
    within the temporary workspace directory. The injected code automatically calls
    `patch_python_tool_call_func` with the provided patch data file when the tool is imported,
    ensuring that all tool calls return the mocked responses for testing or evaluation.
    This code needs to run after the syspath mutation, but before the tool function is decorated.

    Notes:
    - We mutate tool code prior to importing the deliverables into the ToolsRuntimeManager
    - Necessary since Tool execution occurs in a separate external process.
    - The Deliverables are a subset of the pants sandbox tool files, which is a subset
        of the files on disk.  These files are cleaned up after runtime.
    - To save for review, use the `--keep-sandboxes=always` argument for the pants command.
        - Either by manually invoking the `pants` command or modifying the bash script
            you are using to run the command.


    Args:
        tmp_workspace_dir: Path to the temporary workspace directory.
        patch_cfg: PatchConfig instance.
    """

    patch_data_filepath = patch_cfg.patch_data_filepath
    custom_injectable = INJECTABLE.format(patch_data_filepath=patch_data_filepath)

    tools_path = tmp_workspace_dir / "agent_ready_tools/tools"

    # Modify the temp deliverable tool files.
    for root, _, files in tools_path.walk():
        for file in files:
            if not file.endswith(".py"):
                continue

            tool_path = root / file
            tool_path_code = tool_path.read_text()

            # Find first @tool decorator (ignoring comments/docstrings)
            first_tool_line = _find_decorator_line(tool_path_code, "tool")

            if first_tool_line:
                # Inject patching code before the decorator but after the syspath mutation,
                #   which is always added on the top of the file.
                new_code = _inject_code_before_line(
                    tool_path_code, custom_injectable, first_tool_line
                )
                tool_path.write_text(new_code)


def eval_patch_tools_import(
    requirements_file_path: Path,
    targeted_conn_id_map: dict[str, Optional[list[str]]],
    target_snapshot: str,
) -> None:
    """
    If manager_id is defined, targeted_tools list can be retrieved. This block of code uses
    multiprocessing to import the tools in targeted_tools concurrently.

    Args:
        requirements_file_path: The path to the requirements_file.
        targeted_conn_id_map: Map of all tools for a specific manager
            and its required connections ids.
        target_snapshot: Full path to snapshot file to use in the TR.
    """

    tools_data_map = ToolsDataMap().get_tool_name_to_tool_data_map()

    filtered_tools_data_map = {
        tool_name: tools_data
        for tool_name, tools_data in tools_data_map.items()
        if tool_name in targeted_conn_id_map
    }
    tool_name_to_temp_tool_filepath, tmp_workspace_dir = build_client_specific_deliverables(
        filtered_tools_data_map
    )

    # Custom modifications if mock is used.

    inject_tool_patching(tmp_workspace_dir=tmp_workspace_dir, patch_cfg=DEFAULT_PATCH_CONFIG)

    # Copy over the files manually and add them to the deliverables since they aren't caught
    #   within the dependency mapper.
    sandbox_snapshot_code_dir = (
        find_target_directory("agent_ready_tools").parent / SNAPSHOT_UTILS_DEFAULT_DIR
    )
    tmp_utils_tool_snapshot_dir = tmp_workspace_dir / SNAPSHOT_UTILS_DEFAULT_DIR
    shutil.copytree(sandbox_snapshot_code_dir, tmp_utils_tool_snapshot_dir, dirs_exist_ok=True)

    # Copy over mock data into the deliverables. Should reside next to the requests wrapper
    #   module in `agent_ready_tools/lib` so we don't have to do fancy pathfinding.
    tools_mock_cache = tmp_workspace_dir / DEFAULT_PATCH_CONFIG.patch_data_filepath
    shutil.copyfile(target_snapshot, tools_mock_cache)
    assert (
        tools_mock_cache.exists()
    ), f"Patch data has not been copied to deliverables: {tools_mock_cache}"

    multithreaded_args = [
        (
            ToolKind.python,
            str(tool_name_to_temp_tool_filepath[tool_name]),
            tool_app_ids,
            str(requirements_file_path),
            str(tmp_workspace_dir),
        )
        for tool_name, tool_app_ids in targeted_conn_id_map.items()
    ]

    with multiprocessing.Pool(processes=max(multiprocessing.cpu_count() // 2, 1)) as pool:
        pool.starmap(tool_import, multithreaded_args)
