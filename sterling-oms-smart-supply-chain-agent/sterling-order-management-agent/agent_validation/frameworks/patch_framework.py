from datetime import datetime
import os
from pathlib import Path
from typing import Optional

from agent_validation.config.validation_config import FrameworkConfig
from agent_validation.import_manager import ImportPatchManager
from agent_validation.util.group_summaries import build_group_summary_table
from agent_validation.util.logger import get_logger
from ibm_watsonx_orchestrate.cli.commands.evaluations.evaluations_command import evaluate
from import_utils.clear_env import clear_local_env

_logger = get_logger(__name__)
DEFAULT_PATCH_DATA_DIR = "agent_validation/env_patch/data"
DEFAULT_TEST_CASES_DIR = "agent_validation/adk_test_cases"


def _find_patch_data_pair(test_case: Path) -> Optional[Path]:
    """
    Location of the patch data can be derived from the test case config path.

    Args:
        test_case: test case path

    Returns:
        Path if patch data pair is found, else None which will trigger live API mode.
    """

    fixture_path = test_case.with_suffix(".py")
    return fixture_path if fixture_path.exists() else None


def _find_all_test_cases(config_test_suite_paths: list[str]) -> list[Path]:
    """
    From the config paths, if a directory, find all paths to test case config files.

    Args:
        config_test_suite_paths: list of paths to or directories containing test case config files

    Returns:
        List of paths to test case config files
    """

    # Get all the test_suite paths.
    all_test_cases = []
    for test_suite_path_str in config_test_suite_paths:
        test_suite_path = Path(test_suite_path_str)

        if test_suite_path.is_dir():
            for root, _, files in test_suite_path.walk():
                for file in files:
                    if not file.endswith(".json"):
                        continue

                    pants_rel_path = root / file
                    all_test_cases.append(pants_rel_path)

        elif test_suite_path.is_file():
            all_test_cases.append(test_suite_path)

    return all_test_cases


def patch_framework(eval_config: FrameworkConfig, timestamp_format: str) -> str:
    """
    Runner for Eval Framework through the ADK CLI command, but with fixture like patching.

    Run the framework on a per test case basis, so that means load in the tools, run evals,
    then clear env (tools and agents only)
    TODO: add a patch mode for data dumping to logs from live APIs.

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

    # Do a full clear of environment to be safe.
    clear_local_env(ignore_connections=True)

    all_test_cases = _find_all_test_cases(eval_config.test_paths)

    for test_case_path in all_test_cases:

        _logger.info("Clearing env to reduce data pollution between test cases.")
        clear_local_env(ignore_connections=True)

        patch_data_path = _find_patch_data_pair(test_case_path)  # Returns None if not found.
        test_case_patch_env = False
        if patch_data_path is None:
            _logger.info(f"No patch file found, using live APIs. Test case: {test_case_path}")
        else:
            _logger.info(f"Patch file found, patching Tool Responses. Test case: {test_case_path}")
            test_case_patch_env = True

        # Force the Import manager to default to live apis importing.
        for manager_path in eval_config.agent_files:
            ImportPatchManager(
                manager_filepath=manager_path,
                env_setup=eval_config.env_setup,
                env_cleanup=eval_config.env_cleanup,
                patch_env=test_case_patch_env,
                patch_file=patch_data_path,
            ).import_env()

        evaluate(
            test_paths=str(test_case_path),
            output_dir=output_dir,
            user_env_file=str(env_filepath),
        )

        if eval_config.env_cleanup:
            clear_local_env(ignore_connections=True)

    # Rebuild the summaries by grouping them together and print a new table summary.
    output_dir = build_group_summary_table(summary_parent_dir=str(output_dir))

    return output_dir
