import enum
from pathlib import Path
from typing import List


class FileType(enum.StrEnum):
    """Specify filetypes by their extension."""

    JSON = ".json"
    YAML = ".yaml"
    EXCEL = ".xlsx"


def is_file_type(path: str, file_type: FileType) -> bool:
    """
    Check whether a path is a certain FileType.

    Args:
        path: An os.Pathlike instance.
        file_type: A FileType.

    Returns:
        True if the path is this file_type, or false.
    """
    return Path(path).suffix == file_type


def list_all_files(paths: List[str], *, file_types: List[FileType] | None = None) -> List[str]:
    """
    Collects all valid file paths from the given list of files and directories (recursively).

    Args:
        paths: A list of directory/file paths.
        file_types: A list of FileType to specify for the file search.

    Returns:
        A list containing absolute paths to all existing files.
    """

    def filter_is_filetype(path: str, file_types: List[FileType]) -> bool:
        return any(is_file_type(path, ft) for ft in file_types)

    result: List[str] = []
    for path_str in paths:

        path = Path(path_str)
        assert path.exists(), f"The specified file does not exist: {path_str}"

        if path.is_dir():
            for root, _, files in path.walk():
                for file in files:
                    child_filepath = str(root / file)
                    if file_types is None or filter_is_filetype(child_filepath, file_types):
                        result.append(child_filepath)

        elif path.is_file():
            # Only include files of a specified type
            if file_types is not None and not filter_is_filetype(path_str, file_types):
                continue
            result.append(path_str)

    return result
