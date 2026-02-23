"""Common Library for import utils."""

import os
from pathlib import Path

from import_utils.utils.logger import suppress_tool_type_hint_warning

MAX_LOOP_DEPTH = 10


suppress_tool_type_hint_warning()


def find_target_directory(target_dir: str) -> Path:
    """
    Dynamically search directories above this file for a target directory.

    Args:
        target_dir: Target directory to search for.

    Returns:
        Path to the target directory.
    """

    check_path = Path(__file__).resolve().parent
    found_target_parent_dir = None
    for _ in range(0, MAX_LOOP_DEPTH):
        # Get all direct children names in the directory, files and dirs.
        child_list = [Path(d).name for d in check_path.iterdir()]
        if target_dir in child_list:
            found_target_parent_dir = check_path
            break
        else:
            # Not found, so move up in directory structure and check again.
            check_path = check_path.parent

    if found_target_parent_dir is None:
        raise FileNotFoundError(f"Could not find directory of '{target_dir}'.")

    target_path = found_target_parent_dir / target_dir

    if not target_path.exists():
        raise FileNotFoundError(f"Code error. Directory not found '{target_path}'.")
    if not target_path.is_dir():
        raise NotADirectoryError(f"Directory '{target_path}' is not a directory.")

    return target_path


def get_temp_flattener_dir() -> Path:
    """
    Common function to build a path to the local machine's working directory.

    Making sure we don't build temp files in the pants sandbox for debugging purposes.

    Returns:
        Path to the local working directory.
    """
    import_utils_folder_name = Path(__file__).parent.name
    import_utils_local_dir = Path(import_utils_folder_name).resolve()
    tmp_working_dir = import_utils_local_dir / "tmp_flattened_tools"

    # The tmp_flattened_tools directory should already exist; recreate it if missing.
    os.makedirs(str(tmp_working_dir), exist_ok=True)

    return tmp_working_dir


def write_to_tmp_working_dir(
    filename: str,
    output_str: str,
) -> Path:
    """
    Unify where we write temporary files for flattening logic.

    Args:
        filename: filename to exist within the temporary working directory.
        output_str: Output string to write to the temporary working directory.

    Returns:
        Path to the outputted file.
    """
    tmp_working_dir = get_temp_flattener_dir()
    tmp_file_output = tmp_working_dir / filename
    with open(tmp_file_output, "w") as f:
        f.write(output_str)
    return tmp_file_output
