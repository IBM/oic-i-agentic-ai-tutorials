import csv
from pathlib import Path
import sys
from typing import Dict, List

from agent_validation.config.validation_config import FrameworkConfig
from agent_validation.framework import TIMESTAMP_FORMAT
from agent_validation.frameworks.patch_framework import patch_framework
from agent_validation.util.group_summaries import GroupSummaryConstants
from agent_validation.util.logger import get_logger
import typer
from typing_extensions import Annotated

app = typer.Typer(no_args_is_help=True)
logger = get_logger("ThresholdCheck")


def threshold_check(match_rate: float, match_rate_threshold: float) -> None:
    """
    Check threshold against the given match rate. Fail with non-zero status if threshold missed.

    Args:
        match_rate: Match rate
        match_rate_threshold: Match rate threshold
    """

    if match_rate <= match_rate_threshold:
        logger.error(f"match_rate {match_rate} doesn't meet threshold of ({match_rate_threshold})")
        sys.exit(1)
    else:
        logger.info(f"match_rate {match_rate} meets threshold ({match_rate_threshold})")


def _csv_to_dict(summary_csv_path: str) -> List[Dict[str, str]]:
    """
    Loads a CSV file into a list of dictionaries.

    Args:
        summary_csv_path: The path to the CSV file

    Returns:
        Dictionary of CSV rows.
    """
    data = []
    with open(summary_csv_path, "r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            data.append(row)
    return data


def _find_most_recent_summary_file(adk_output_directory: str) -> Path:
    """
    Broad search for the summary file within the output directory.

    Relies on framework function to return the output directory with the timestamp.
    ADK v1.13.0 introduces their own timestamp, but we don't have easy access to it.
    So for now the output directory for ADK Framework will have double timestamps.
    e.g. agent_validation/test_run/20251014_1405/2025-10-14_14-07-08/summary_metrics.csv

    Args:
        adk_output_directory: The output directory path in string format

    Returns:
        Path object of summary file.
    """
    adk_output_directory_path = Path(adk_output_directory)
    for root, _, files in adk_output_directory_path.walk():
        for file in files:
            if file == GroupSummaryConstants.SUMMARY_REPORT:
                return root / file

    raise FileNotFoundError(
        f"{GroupSummaryConstants.SUMMARY_REPORT} not found in {adk_output_directory}"
    )


def _adk_threshold_check(config: FrameworkConfig) -> None:
    """
    Runner for ADK Eval Framework with the added task of generating a metric for exiting with non-
    zero status if failure detected.

    Args:
        config: ADK Eval Config Dataclass
    """
    adk_output_directory = patch_framework(config, TIMESTAMP_FORMAT)

    summary_report = _find_most_recent_summary_file(adk_output_directory)

    csv_data = _csv_to_dict(str(summary_report))

    success_percent = float(csv_data[-1]["Journey Success"].replace("%", ""))
    success_rate = success_percent / 100
    threshold_check(success_rate, match_rate_threshold=config.threshold)


@app.command(name="run_threshold")
def framework_threshold_runner(
    config_path: Annotated[
        str, typer.Option("--config_path", help="Path to the validation config YAML file")
    ] = "agent_validation/config/adk_smoke_validation_config.yaml",
) -> None:
    """Run the validation framework for CI/CD check, failing on success metric threshold."""

    config = FrameworkConfig.load(config_path)
    _adk_threshold_check(config)


if __name__ == "__main__":
    app()
