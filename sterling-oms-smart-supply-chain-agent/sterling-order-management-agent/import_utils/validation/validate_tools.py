"""Library for validation tool kit for Orchestrate PythonTool definitions."""

import logging
from pprint import pformat
from typing import Tuple

from import_utils.utils.tools_data_mapper import ToolsDataMap


def _get_logger() -> logging.Logger:
    """
    Setup and get a formatted logger.

    If we want to output the log, update logging.

    Returns:
        logger with a specific format
    """
    # Setup logger format
    validator_logger = logging.getLogger("ToolsValidator")
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    validator_logger.addHandler(handler)
    return validator_logger


def validate_tools(tools_map: ToolsDataMap, raise_exc: bool = True) -> Tuple[bool, str]:
    """
    Check if there are any invalid tools and raise exception. Use in case we need a state where
    there are no invalid tools.

    Args:
        tools_map: tools data map
        raise_exc: Default behavior is to raise exception if invalid tools found. Can be used to
            bypass raise.

    Returns:
        Status of check and error message if invalid tools found.
    """
    invalid_tools = tools_map.invalid_tools
    if not invalid_tools:
        return True, ""

    err_data = {k: [str(v_data.file_path) for v_data in v] for k, v in invalid_tools.items()}
    err_msg = str(pformat(err_data))

    if raise_exc:
        assert not invalid_tools, f"Collisions detected: \n{err_msg}"

    return False, err_msg


if __name__ == "__main__":

    tools_mapper = ToolsDataMap()
    validate_tools(tools_mapper)

    logger = _get_logger()
    logger.info("SUCCESS - No Collisions Found")
