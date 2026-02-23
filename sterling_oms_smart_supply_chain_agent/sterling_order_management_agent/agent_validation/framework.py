from pathlib import Path
from typing import Optional

from agent_validation.config.validation_config import FrameworkConfig
from agent_validation.frameworks.adk_framework import adk_framework
from agent_validation.frameworks.patch_framework import patch_framework
from agent_validation.util.logger import get_logger
from agent_validation.util.mock_generator import (
    generate_mock_from_config,
    generate_mock_from_test_case,
)
import typer
from typing_extensions import Annotated

MAX_THREAD = 8  # TODO wasn't able to find documentation on the limit of number of connections to the server. Using 8 as a default as it has been tested to run fine.

TIMESTAMP_FORMAT = "%Y%m%d_%H%M"
logger = get_logger(verbose=True)
app = typer.Typer(no_args_is_help=True)


@app.command(name="adk")
def adk_runner(config_path: str) -> None:
    """
    Run the adk evaluations framework.

    Args:
        config_path: Path to the validation config YAML file
    """

    config = FrameworkConfig.load(config_path)
    assert config is not None, f"Invalid config: {config_path}"
    adk_framework(config, TIMESTAMP_FORMAT)


@app.command(name="patch")
def adk_patch_runner(config_path: str) -> None:
    """
    Run the adk evaluations framework with patching.

    Args:
        config_path: Path to the validation config YAML file
    """

    config = FrameworkConfig.load(config_path)
    assert config is not None, f"Invalid config: {config_path}"
    patch_framework(config, TIMESTAMP_FORMAT)


@app.command(name="patch-tool")
def patch_tool(
    config_path: Annotated[
        str,
        typer.Option("--config_path", help="Path to the tool call config YAML/JSON file"),
    ],
    output_path: Annotated[
        Optional[str],
        typer.Option("--output_path", help="Path to write the generated mock file"),
    ] = None,
) -> None:
    """
    Generate a mock file by calling a tool with specified arguments.

    Args:
        config_path: Path to the tool call config YAML/JSON file (like call_tool_config.yaml)
        output_path: Optional path to write the generated mock file. If not provided, prints to stdout.
    """

    generate_mock_from_config(config_path, output_path)


@app.command(name="patch-test-case")
def patch_test_case(
    test_case_path: Annotated[
        str,
        typer.Option("--test_case_path", help="Path to the ADK test case JSON file"),
    ],
    output_path: Annotated[
        Optional[str],
        typer.Option("--output_path", help="Path to write the generated mock file"),
    ] = None,
) -> None:
    """
    Generate mock file from an ADK test case JSON file.

    Extracts all tool calls from the test case and generates fixture functions for each.

    Args:
        test_case_path: Path to the ADK test case JSON file
        output_path: Optional path to write the generated mock file. If not provided, prints to stdout.
    """

    generate_mock_from_test_case(test_case_path, output_path)


@app.command(name="patch-test-suite")
def patch_test_suite(config_path: str) -> None:
    """
    Generate patch data file from a Framework config yaml.

    Extracts all test case files from the test_paths in the config then generate a patch file per
    test cases.

    Args:
        config_path: Path to the validation config YAML file
    """
    config = FrameworkConfig.load(config_path)
    for test_file in config.test_suite_files:
        logger.info(f"Creating Patch for {test_file}")
        output_test_path = Path(test_file).with_suffix(".py")
        if output_test_path.exists():
            logger.info(f"Skipping {str(output_test_path)}")
            continue

        patch_test_case(test_file, str(output_test_path))


if __name__ == "__main__":
    app()
