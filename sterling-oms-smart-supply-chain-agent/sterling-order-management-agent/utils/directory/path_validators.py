import pathlib


def is_valid_dir_path(path: pathlib.Path | str) -> pathlib.Path | str:
    """
    Custom dir path validator.

    Args:
        path: the path to validate.

    Returns:
        the validated path
    """
    _path: pathlib.Path = path if isinstance(path, pathlib.Path) else pathlib.Path(path)
    if _path.exists() and _path.is_dir():
        return path
    else:
        raise ValueError(f"'{path}' is not a valid directory")


def is_valid_filepath(path: pathlib.Path | str) -> pathlib.Path | str:
    """
    Custom filepath validator.

    Args:
        path: the filepath to validate.

    Returns:
        the validated filepath
    """
    _path: pathlib.Path = path if isinstance(path, pathlib.Path) else pathlib.Path(path)
    if _path.exists() and _path.is_file():
        return path
    raise ValueError(f"'{path}' is not a valid filepath")


def is_valid_excel_filepath(path: pathlib.Path | str) -> pathlib.Path | str:
    """
    Custom Excel filepath validator.

    Args:
        path: the Excel filepath to validate.

    Returns:
        the validated Excel filepath
    """
    _path = path if isinstance(path, pathlib.Path) else pathlib.Path(path)
    excel_suffixes = [".xls", ".xlsb", ".xlsm", ".xlsx"]
    if is_valid_filepath(path) and _path.suffix.lower() in excel_suffixes:
        return path
    raise ValueError(f"'{path}' is not a valid Excel filepath")
