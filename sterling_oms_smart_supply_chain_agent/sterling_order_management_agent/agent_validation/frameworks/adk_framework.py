from datetime import datetime
import os
from pathlib import Path

from agent_validation.config.validation_config import FrameworkConfig
from agent_validation.import_manager import ImportManager
from agent_validation.util.logger import get_logger
from ibm_watsonx_orchestrate.cli.commands.evaluations.evaluations_command import evaluate
from import_utils.clear_env import clear_local_env

_logger = get_logger(__name__)


def adk_framework(eval_config: FrameworkConfig, timestamp_format: str) -> str:
    """
    Runner for Eval Framework through the ADK CLI command.

    Args:
        eval_config: config data
        timestamp_format: timestamp format for test cases output

    Returns:
        Output directory for evaluations run data and summary.
    """

    timestamp = datetime.now().strftime(timestamp_format)
    output_dir = os.path.join(eval_config.output_dir, timestamp)

    env_filepath = Path(eval_config.env_file).resolve()
    assert env_filepath.exists(), f"Environment file cannot be found, place it at: {env_filepath}"

    assert (
        len(eval_config.test_paths) == 1
    ), "Only accepts 1 path, if multiple tests cases needed, provide directory path."

    # Run import manager to load all tools from agent files
    for manager_path in eval_config.agent_files:
        ImportManager(
            manager_filepath=manager_path,
            env_setup=eval_config.env_setup,
            env_cleanup=eval_config.env_cleanup,
        ).import_env()

    evaluate(
        test_paths=eval_config.test_paths[0],
        output_dir=output_dir,
        user_env_file=str(env_filepath),
    )

    if eval_config.env_cleanup:
        clear_local_env(ignore_connections=True)

    return output_dir
