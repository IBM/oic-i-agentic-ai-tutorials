import os
from pathlib import Path
import sys

from ibm_watsonx_orchestrate.cli.config import DEFAULT_CONFIG_FILE, DEFAULT_CONFIG_FILE_FOLDER
from ibm_watsonx_orchestrate.client.utils import is_local_dev


def in_adk_env() -> bool:
    """
    Determines whether this code is running in a local ADK environment.

    Returns:
        Whether the env is a local ADK env.
    """
    # can get permission errors when orchestrate tries to read cfg file to determine if local
    config_path = Path(DEFAULT_CONFIG_FILE_FOLDER) / DEFAULT_CONFIG_FILE
    try:
        if config_path.exists() and os.access(str(config_path), os.R_OK):
            if is_local_dev():
                return True
    except (
        PermissionError,
        KeyError,
        AttributeError,
    ):  # Local envs should be able to access the config
        pass
    return False


def in_pants_env() -> bool:
    """
    Determines whether this code is running in a pants env (executed via `pants run ...`, `pants
    test ...` or `pants repl ...`). `pants run ...` and `pants repl ...` invocations don't seem to
    use a tmp sandbox dir, but do have pants-related env vars.

    Returns:
        Whether the env is a pants env.
    """
    return "PANTS_VERSION" in os.environ or "pants-sandbox" in os.getcwd()


def is_running_export_catalog() -> bool:
    """
    Determines whether this code is running as part of the export_catalog_cmd.py script. Used to
    ensure app-id publisher suffix is preserved in catalog exports.

    Returns:
        Whether the current process is running export_catalog_cmd.py
    """
    for arg in sys.argv:
        if "export_catalog_cmd.py" in arg:
            return True
    return False
