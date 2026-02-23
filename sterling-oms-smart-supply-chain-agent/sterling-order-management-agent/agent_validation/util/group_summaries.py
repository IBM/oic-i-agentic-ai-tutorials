import csv
import dataclasses
import json
from pathlib import Path
import shutil
import sys
from typing import Any

from agent_validation.util.logger import get_logger
from agent_validation.util.summary_to_console import summary_to_console
from rich.table import Table
from rich.text import Text
from wxo_agentic_evaluation.metrics.metrics import TextMatchType, ToolCallAndRoutingMetrics
import yaml

_logger = get_logger(__name__)


@dataclasses.dataclass
class GroupSummaryConstants:
    """Contains constants for matching files to grouping action."""

    KB_BASE_METRICS_DIR = "knowledge_base_metrics/knowledge_base_detailed_metrics.json"
    KB_SUMMARY_FILE = "knowledge_base_summary_metrics.json"
    MESSAGES_DIR = "messages"
    CONFIG_FILE = "config.yml"
    SUMMARIES_CSV = "summary_metrics.csv"
    MISSING_SUMMARIES_CSV = "missing_summary_metrics.csv"
    SUMMARY_REPORT = "summary_report.csv"
    FAILED_TEST_CASE_PATHS_YAML = "failed_test_case_paths.yaml"


def _merge_json_files(test_case_json_path: Path, all_cases_json_path: Path) -> None:
    """
    Take a json file for a single test case and combine that into a json that covers all test cases.

    Args:
        test_case_json_path: Path to a json for a single test case.
        all_cases_json_path: Path to the new json for all test cases in group.
    """
    if test_case_json_path.exists():

        all_cases_json_path.parent.mkdir(parents=True, exist_ok=True)
        if all_cases_json_path.exists():
            new_data = json.load(open(all_cases_json_path))
        else:
            new_data = {}

        test_case_json_data = json.load(open(test_case_json_path))

        new_data.update(test_case_json_data)
        json.dump(new_data, open(all_cases_json_path, "w"))

    else:
        shutil.copy2(test_case_json_path, all_cases_json_path)


def _merge_summary_metrics_csvs(test_case_csv_path: list[Path], all_tests_csv_path: Path) -> None:
    """
    Take a csv file for a single test case and combine that into a csv that covers all test cases.

    Args:
        test_case_csv_path: list of all Path objs to a json for a single test case.
        all_tests_csv_path: Path to the new json for all test cases in group.
    """

    csv_data_new_metrics = []
    for test_case_csv in test_case_csv_path:

        config_pair = test_case_csv.parent / GroupSummaryConstants.CONFIG_FILE
        config_data = yaml.safe_load(config_pair.read_text())
        test_paths = config_data["test_paths"]

        # Get Metric data from summary
        csv_data_test_case_metric: list[dict[str, Any]] = list(
            csv.DictReader(open(test_case_csv, "r"))
        )

        for dict_metric in csv_data_test_case_metric:

            # Position the new Agent field in the beginning of the dict.
            list_order = list(dict_metric.items())
            list_order.insert(0, ("agent", "Not Found"))
            dict_order = dict(list_order)

            # Since dataset_name is built from the test_path, do the reverse to find the path to the test case json
            expected_test_case_config = dict_metric["dataset_name"] + ".json"
            for test_path in test_paths:

                # From the test case json, get the agent that it uses.
                if expected_test_case_config == Path(test_path).name:
                    jdata = json.load(open(test_path))
                    agent_name = jdata["agent"]
                    dict_order["agent"] = agent_name

                    csv_data_new_metrics.append(dict_order)

    if csv_data_new_metrics:

        writer = csv.DictWriter(
            f=all_tests_csv_path.open("w", newline=""),
            fieldnames=csv_data_new_metrics[0].keys(),
        )
        writer.writeheader()
        writer.writerows(csv_data_new_metrics)


def _merge_config_yaml(test_case_config_path: Path, all_tests_config_path: Path) -> None:
    """
    Take a config yaml file for a single test case and merge that into a yaml that covers all test
    cases.

    If the file does not exist, then just copy it over to a new yaml file.
    We are only merging "test_paths" of the entries in the config yaml, the rest of the data
    should be consistent between test cases.

    Args:
        test_case_config_path: Path to the config yaml for a single test case.
        all_tests_config_path: Path to the new config yaml for all test cases in group.
    """
    if all_tests_config_path.exists():

        yaml_test_case_data = yaml.safe_load(open(test_case_config_path, "r"))
        yaml_all_tests_data = yaml.safe_load(open(all_tests_config_path, "r"))

        yaml_all_tests_data["test_paths"].extend(yaml_test_case_data["test_paths"])
        yaml_all_tests_data["test_paths"] = list(set(yaml_all_tests_data["test_paths"]))

        yaml.dump(
            yaml_all_tests_data,
            all_tests_config_path.open("w"),
            default_flow_style=False,
            sort_keys=False,
        )

    else:
        shutil.copy2(test_case_config_path, all_tests_config_path)


def _build_missing_datasets_summary(full_summary_dir: Path) -> None:
    """
    Parse through the config and build a list of potential dataset names.  Find the missing names
    from the full summary to determine tests with critical failures, then build a new summary
    containing all missing datasets.

    Args:
        full_summary_dir: Path to the full summary directory after it's been merged
    """
    full_config_path = full_summary_dir / GroupSummaryConstants.CONFIG_FILE
    assert full_config_path.exists(), "full_config_path does not exist"
    cfg_data = yaml.safe_load(open(full_config_path, "r"))
    cfg_test_paths = cfg_data.get("test_paths", [])

    potential_datasets: dict[str, str] = {}
    dataset_name_collisions = []
    for test_path in cfg_test_paths:
        dataset_name = Path(test_path).with_suffix("").name
        if dataset_name in potential_datasets:
            dataset_name_collisions.append((test_path, potential_datasets[dataset_name]))
        potential_datasets[dataset_name] = test_path

    csv_data = list(
        csv.DictReader(open(full_summary_dir / GroupSummaryConstants.SUMMARIES_CSV, "r"))
    )
    valid_datasets = [c["dataset_name"] for c in csv_data]

    missing_datasets = []
    missing_test_cases = []
    for k_dataset_name, v_testcase_path in potential_datasets.items():
        if k_dataset_name not in valid_datasets:
            missing_datasets.append(ToolCallAndRoutingMetrics(dataset_name=k_dataset_name))
            missing_test_cases.append(v_testcase_path)

    metrics = [metric.model_dump() for metric in missing_datasets]
    if not metrics:
        return

    output_file = full_summary_dir / GroupSummaryConstants.MISSING_SUMMARIES_CSV
    header = list(metrics[0].keys())

    with open(output_file, "w") as file:
        csv_writer = csv.writer(file)
        csv_writer.writerow(header)
        for entry in metrics:
            row_data = []
            for name in header:
                data = entry[name]

                # Bug with enum serialization, so sanitize data.
                if name == "text_match" and isinstance(data, TextMatchType):
                    data = data.value

                row_data.append(data)

            csv_writer.writerow(row_data)

    if missing_test_cases:
        failed_test_cases_yaml = (
            full_summary_dir / GroupSummaryConstants.FAILED_TEST_CASE_PATHS_YAML
        )
        failed_yaml_data = {
            "test_paths": missing_test_cases,
        }
        yaml.dump(failed_yaml_data, failed_test_cases_yaml.open("w+"), default_flow_style=False)

    if dataset_name_collisions:
        err_msg = "Dataset name collisions detected on test paths: \n"
        for key_collision, on_key in dataset_name_collisions:
            err_msg += f"    {key_collision}: {on_key}\n"
        _logger.error(err_msg)


def _rich_table_to_list_of_dicts(table: Table) -> list[dict[str, Any]]:
    """
    Convert a rich.Table to a list of dictionaries (one dict per row).

    Args:
        table: A rich.Table object

    Returns:
        List of dictionaries where each dict represents a row
    """

    def _extract_text(value: Any) -> str:
        """
        Extract plain text from rich objects or return string representation.

        Args:
            value: Any value that might be a rich object or plain value

        Returns:
            Plain text string representation
        """
        if isinstance(value, Text):
            return value.plain
        elif isinstance(value, str):
            return value
        else:
            return str(value)

    # Extract column headers
    columns = [_extract_text(col.header) for col in table.columns]

    # Get the number of rows
    if not table.columns:
        return []

    # pylint: disable=protected-access
    num_rows = len(table.columns[0]._cells)

    # Build list of row dictionaries
    result = []
    for row_index in range(num_rows):
        row_dict = {}
        for col_index, col_name in enumerate(columns):
            cell = table.columns[col_index]._cells[row_index]
            row_dict[col_name] = _extract_text(cell)
        result.append(row_dict)

    return result


def _list_of_dicts_to_csv(list_of_dicts: list[dict[str, Any]], output_file: Path) -> None:
    header = list(list_of_dicts[0].keys())

    with open(output_file, "w") as file:
        csv_writer = csv.writer(file)
        csv_writer.writerow(header)
        for entry in list_of_dicts:
            csv_writer.writerow([entry[name] for name in header])


def group_summaries(summary_parent_dir: str, directory_name: str = "summary") -> str:
    """
    Provided a path for a directory containing the summaries that were run on a per-test basis
    through the ADK Evaluations platform, regroup all the data into a single summary directory.

    Create a new directory using the original folder, but with a new tag appended to it.
    This way we can preserve the original data.

    Args:
        summary_parent_dir: String path to directory containing the summaries that were
            run on a per-test basis.  Use relative path for pants to map to local environment
            and not the pants sandbox.
        directory_name: String name of the new directory to create.

    Returns:
        New directory containing collated summary.
    """

    summary_parent_dir_path = Path(summary_parent_dir)
    full_summary_dir = summary_parent_dir_path / directory_name

    # Compile all possible files so we aren't scanning the new summary files as we create them.
    all_summary_files = []
    for root, _, files in summary_parent_dir_path.walk():
        for file in files:

            if root.parent == directory_name:
                continue

            file_path = root / file
            all_summary_files.append(file_path)

    full_summary_dir.mkdir(parents=True, exist_ok=True)

    list_summary_metrics = []

    # Merge all existing files into the full summary directory.

    for file_path in all_summary_files:
        file = file_path.name
        root = file_path.parent

        # Combine test case specific knowledge base detailed metrics into all tests json.
        if root.name == Path(GroupSummaryConstants.KB_BASE_METRICS_DIR).parent.name:
            new_kb_details_file = full_summary_dir / GroupSummaryConstants.KB_BASE_METRICS_DIR
            _merge_json_files(file_path, new_kb_details_file)

        # Combine test_case specific knowledge base summary metric into all tests json.
        if GroupSummaryConstants.KB_SUMMARY_FILE == file:
            new_kb_details_file = full_summary_dir / GroupSummaryConstants.KB_SUMMARY_FILE
            _merge_json_files(file_path, new_kb_details_file)

        # Combine all summary metrics into a single csv file
        if file == GroupSummaryConstants.SUMMARIES_CSV:
            list_summary_metrics.append(file_path)

        # Combine all `test_paths` into the config.yml, all the other data should be the same
        if file == GroupSummaryConstants.CONFIG_FILE:
            new_config_path = full_summary_dir / GroupSummaryConstants.CONFIG_FILE
            _merge_config_yaml(file_path, new_config_path)

        # Copy all messages into the same directory, no need to modify files
        if root.name == GroupSummaryConstants.MESSAGES_DIR:
            new_messages_dir = full_summary_dir / root.name
            new_messages_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, new_messages_dir / file)

    new_summary_metrics_csv_path = full_summary_dir / GroupSummaryConstants.SUMMARIES_CSV
    _merge_summary_metrics_csvs(list_summary_metrics, new_summary_metrics_csv_path)

    # Find the missing data sets and create a missing dataset csv.
    _build_missing_datasets_summary(full_summary_dir)

    return str(full_summary_dir)


def build_group_summary_table(summary_parent_dir: str, directory_name: str = "summary") -> str:
    """
    Main entry point for group_summaries. Consolidate the chunked summaries and print to console
    using the evaluations format.

    Args:
        summary_parent_dir: Path to the directory containing the fragmented summaries dirs.
        directory_name: String name of the new directory to create within summary_parent_dir

    Returns:
        Path to the newly grouped summary files.
    """
    full_summary_dir = group_summaries(summary_parent_dir, directory_name)
    summary_csv = Path(full_summary_dir) / GroupSummaryConstants.SUMMARIES_CSV
    missing_summary_csv = Path(full_summary_dir) / GroupSummaryConstants.MISSING_SUMMARIES_CSV

    summary_table = summary_to_console(summary_csv, missing_summary_csv)

    if summary_table:
        summary_table.print()

        # Save the output table for later review.
        full_summary_table = _rich_table_to_list_of_dicts(summary_table.table)
        summary_table_csv = Path(full_summary_dir) / GroupSummaryConstants.SUMMARY_REPORT
        _list_of_dicts_to_csv(full_summary_table, summary_table_csv)

    return full_summary_dir


if __name__ == "__main__":
    # Usage: pants run agent_validation/util/group_summaries.py -- /path/to/summary_parent
    _summary_parent_dir = Path(sys.argv[1])
    assert (
        _summary_parent_dir.is_dir()
    ), f"Summary Directory is not a directory: {_summary_parent_dir}"

    # Clear old summary if found.
    p_sum = _summary_parent_dir / "summary"
    if p_sum.exists():
        shutil.rmtree(p_sum)

    build_group_summary_table(summary_parent_dir=str(_summary_parent_dir))
