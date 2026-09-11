"""Test suite for group_summaries module with pytest fixtures."""

# pylint: disable=redefined-outer-name
import csv
import json
from pathlib import Path
from typing import Generator, Optional
from unittest.mock import patch

from agent_validation.util.group_summaries import (
    GroupSummaryConstants,
    build_group_summary_table,
    group_summaries,
)
import pytest
from wxo_agentic_evaluation.metrics.metrics import ToolCallAndRoutingMetrics
import yaml


def _build_test_file_structure(test_case_id: int, test_case_parent_dir: Path) -> Path:
    """
    Helper to create a temporary directory structure mimicking ADK evaluation summaries.

    This fixture creates a test case directory, each containing:
    - knowledge_base_metrics/knowledge_base_detailed_metrics.json
    - knowledge_base_summary_metrics.json
    - summary_metrics.csv
    - config.yml
    - messages/ directory with message files

    Args:
        test_case_id: test case identifier
        test_case_parent_dir: parent directory of test case that we will be targeting.

    Returns:
        test case directory path
    """

    test_case_config_dir = test_case_parent_dir.parent / "test_case_configs"
    test_case_config_dir.mkdir(parents=True, exist_ok=True)
    test_case_dir = test_case_parent_dir / f"test_case_{test_case_id}"
    test_case_dir.mkdir(parents=True, exist_ok=True)

    # Create knowledge base metrics directory and file
    kb_metrics_dir = test_case_dir / GroupSummaryConstants.KB_BASE_METRICS_DIR
    kb_metrics_dir.parent.mkdir(exist_ok=True)
    kb_detailed = test_case_dir / GroupSummaryConstants.KB_BASE_METRICS_DIR
    kb_detailed.touch(exist_ok=True)
    kb_detailed.write_text(
        json.dumps(
            {
                f"kb_entry_{test_case_id}": {
                    "score": 0.85 + test_case_id * 0.05,
                    "metadata": f"test_data_{test_case_id}",
                }
            }
        )
    )

    # Create knowledge base summary file
    kb_summary = test_case_dir / GroupSummaryConstants.KB_SUMMARY_FILE
    kb_summary.write_text(
        json.dumps(
            {
                f"summary_{test_case_id}": {
                    "total_entries": test_case_id * 10,
                    "avg_score": 0.85 + test_case_id * 0.05,
                }
            }
        )
    )

    # Create summary CSV with evaluation metrics
    summary_csv = test_case_dir / GroupSummaryConstants.SUMMARIES_CSV
    with summary_csv.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "dataset_name",
                "total_steps",
                "llm_step",
                "total_tool_calls",
                "expected_tool_calls",
                "correct_tool_calls",
                "relevant_tool_calls",
                "total_routing_calls",
                "relevant_routing_calls",
                "text_match",
                "is_success",
                "avg_resp_time",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "dataset_name": f"test_case_{test_case_id}",
                "total_steps": str(10 + test_case_id),
                "llm_step": str(5 + test_case_id),
                "total_tool_calls": str(3 + test_case_id),
                "expected_tool_calls": str(10),
                "correct_tool_calls": str(9),
                "relevant_tool_calls": str(10),
                "total_routing_calls": str(10),
                "relevant_routing_calls": str(8 + test_case_id),
                "text_match": (
                    "Summary Matched" if test_case_id % 2 == 0 else "Summary MisMatched"
                ),
                "is_success": str(test_case_id % 2 == 0),
                "avg_resp_time": str(1.5 + test_case_id * 0.1),
            }
        )

    # Create config YAML file
    config_file = test_case_dir / GroupSummaryConstants.CONFIG_FILE
    test_case_config_path = f"{test_case_config_dir}/test_case_{test_case_id}.json"
    config_data = {
        "test_paths": [test_case_config_path],
        "agent_name": f"test_agent_{test_case_id}",
        "evaluation_type": "standard",
    }
    config_file.write_text(yaml.dump(config_data, default_flow_style=False))
    skeleton_config_data = {
        "agent": f"agent_{test_case_id}",
    }
    json.dump(skeleton_config_data, open(test_case_config_path, "w+"))

    # Create messages directory with message files
    messages_dir = test_case_dir / "messages"
    messages_dir.mkdir()
    for j in range(1, 3):
        message_file = messages_dir / f"message_{test_case_id}_{j}.json"
        message_file.write_text(
            json.dumps(
                {
                    "message_id": f"{test_case_id}_{j}",
                    "content": f"Test message {j} for case {test_case_id}",
                    "timestamp": f"2024-01-{test_case_id:02d}T12:00:00Z",
                }
            )
        )
        assert message_file.exists()

    return test_case_dir


@pytest.fixture
def temp_summary_structure(
    tmp_path: Path,
) -> Generator[Path, None, None]:
    """
    Create a temporary directory structure mimicking ADK evaluation summaries.

    This fixture creates multiple test case directories, each containing:
    - knowledge_base_metrics/knowledge_base_detailed_metrics.json
    - knowledge_base_summary_metrics.json
    - summary_metrics.csv
    - config.yml
    - messages/ directory with message files

    Args:
        tmp_path: pytest's built-in temporary directory fixture

    Yields:
        Path to the parent directory containing all test case directories
    """

    test_case_parent_dir = tmp_path / "summaries_parent"
    test_case_parent_dir.mkdir(parents=True, exist_ok=True)

    # Create test case directories
    test_case_dirs = []
    for t_id in range(1, 5):
        tmp_summary_dir = _build_test_file_structure(t_id, test_case_parent_dir)
        test_case_dirs.append(tmp_summary_dir)

    # Remove the summary metric csv considering it as a critical failure.
    last_summary_csv = test_case_dirs[-1] / GroupSummaryConstants.SUMMARIES_CSV
    last_summary_csv.unlink()

    group_summary_dir = group_summaries(str(test_case_parent_dir))
    assert Path(group_summary_dir).is_dir(), "Directory does not exist"

    yield Path(group_summary_dir)


# Test functions for group_summaries()


def test_group_summaries_merges_csv_files(
    temp_summary_structure: Path,
) -> None:
    """
    Test that summary CSV files are properly merged.

    Verifies that all rows from individual test case CSVs are combined into a single CSV file with
    headers preserved and all data rows present.
    """
    print(temp_summary_structure)

    summary_csv_fragments = []
    full_summary_csv: Optional[Path] = None
    for root, _, files in temp_summary_structure.walk():
        for file in files:
            if file == "summary_metrics.csv":
                if root.name == "summary":
                    full_summary_csv = root / file
                else:
                    summary_csv_fragments.append(root / file)

    assert full_summary_csv is not None, f"Full csv was not created: {full_summary_csv}"

    full_sum_csv_text = full_summary_csv.read_text()
    for summary_frag in summary_csv_fragments:
        frag_text = summary_frag.read_text()
        for frag_line in frag_text.split("\n"):
            assert frag_line in full_sum_csv_text, f"Full Summary missing data: {full_summary_csv}"


def test_group_summaries_merges_knowledge_base_detailed_metrics(
    temp_summary_structure: Path,
) -> None:
    """
    Test that knowledge base detailed metrics JSON files are properly merged.

    Verifies that all KB detailed metrics from individual test cases are combined into a single JSON
    file with all entries preserved.
    """

    kb_json_list = []
    full_kb_file: Optional[Path] = None
    for root, _, files in temp_summary_structure.walk():
        for file in files:
            if file == "knowledge_base_detailed_metrics.json":
                if root.parent.name == "summary":
                    full_kb_file = root / file
                else:
                    kb_json_list.append(root / file)

    assert full_kb_file is not None, f"Full kb_metrics was not created: {full_kb_file}"

    full_data = json.loads(full_kb_file.read_text())
    for kb_fragment in kb_json_list:
        frag_data = json.loads(kb_fragment.read_text())
        for key, val in frag_data.items():
            assert (
                key in full_data and val == full_data[key]
            ), f"kb detailed metrics JSON data missing: {key}"


def test_group_summaries_merges_knowledge_base_summary_metrics(
    temp_summary_structure: Path,
) -> None:
    """
    Test that knowledge base summary metrics JSON files are properly merged.

    Verifies that KB summary metrics from all test cases are combined into a single JSON file.
    """
    kb_json_list = []
    full_kb_file: Optional[Path] = None
    for root, _, files in temp_summary_structure.walk():
        for file in files:
            if file == "knowledge_base_summary_metrics.json":
                if root.name == "summary":
                    full_kb_file = root / file
                else:
                    kb_json_list.append(root / file)

    assert full_kb_file is not None, f"Full kb_metrics was not created: {full_kb_file}"

    full_data = json.loads(full_kb_file.read_text())
    for kb_fragment in kb_json_list:
        frag_data = json.loads(kb_fragment.read_text())
        for key, val in frag_data.items():
            assert (
                key in full_data and val == full_data[key]
            ), f"kb summary metrics JSON data missing: {key}"


def test_group_summaries_merges_config_yaml_test_paths(
    temp_summary_structure: Path,
) -> None:
    """
    Test that config YAML files are merged with test_paths combined.

    Verifies that the test_paths list from all config files are merged while other config values
    remain consistent.
    """
    config_yamls_list = []
    full_config_yaml: Optional[Path] = None
    for root, _, files in temp_summary_structure.walk():
        for file in files:
            if file == "config.yml":
                if root.name == "summary":
                    full_config_yaml = root / file
                else:
                    config_yamls_list.append(root / file)

    assert full_config_yaml is not None, f"Full config was not created: {full_config_yaml}"

    full_data = yaml.safe_load(full_config_yaml.read_text())
    full_paths = set(full_data.pop("test_paths"))
    for fragment in config_yamls_list:
        frag_data = yaml.safe_load(fragment.read_text())
        frag_paths = frag_data.pop("test_paths")
        assert full_data == frag_data, "Config yaml consistent data is inconsistent"
        for frag_path in frag_paths:
            assert frag_path in full_paths, "Not all paths in config were merged"


def test_group_summaries_copies_message_files(
    temp_summary_structure: Path,
) -> None:
    """
    Test that message files are copied to the summary messages directory.

    Verifies that all message JSON files from individual test cases are copied into a single
    messages directory without modification.
    """
    messages_fragments_list = []
    full_messages_list = []

    for root, _, files in temp_summary_structure.walk():
        for file in files:
            if root.name == "messages":
                if root.parent.name == "summary":
                    full_messages_list.append(file)
                else:
                    messages_fragments_list.append(file)

    assert full_messages_list, "No messages found in merged summary directory."

    assert all(
        f in full_messages_list for f in messages_fragments_list
    ), "Message files not found in merged summary directory."


def test_missing_csv(
    temp_summary_structure: Path,
) -> None:
    """Test that missing data csv is found and added into a new missing csv file."""
    full_summary_csv = temp_summary_structure / GroupSummaryConstants.SUMMARIES_CSV
    missing_csv_file = temp_summary_structure / GroupSummaryConstants.MISSING_SUMMARIES_CSV
    config_file = temp_summary_structure / GroupSummaryConstants.CONFIG_FILE

    assert full_summary_csv.exists(), "Full summary csv should have been grouped and created."
    assert config_file.exists(), "Merged config should have been created containing all test cases."
    assert missing_csv_file.exists(), "Missing summaries csv should have been created."

    full_summary_csv_dict = csv.DictReader(open(full_summary_csv))
    missing_csv_file_dict = csv.DictReader(open(missing_csv_file))
    config_file_dict = yaml.safe_load(open(config_file))

    for row in missing_csv_file_dict:
        assert (
            row not in full_summary_csv_dict
        ), f"Missing report row should not be in the full summary."

    config_test_names = {Path(t).with_suffix("").name for t in config_file_dict["test_paths"]}

    for r in missing_csv_file_dict:
        assert (
            r["dataset_name"] in config_test_names
        ), "Test case should be defined in the config even though it is missing a summary csv file."


def test_summary_report(
    temp_summary_structure: Path,
) -> None:
    """Test that the summary report is generated from the merged and missing summaries."""
    full_summary_csv = temp_summary_structure / GroupSummaryConstants.SUMMARIES_CSV
    missing_csv_file = temp_summary_structure / GroupSummaryConstants.MISSING_SUMMARIES_CSV

    # Mock group_summaries to prevent it from running again (already ran in fixture)
    with patch("agent_validation.util.group_summaries.group_summaries") as mock_group_summaries:
        mock_group_summaries.return_value = str(temp_summary_structure)

        # Call build_group_summary_table - it will use mocked group_summaries
        # but will still process the CSV files that already exist
        build_group_summary_table(summary_parent_dir=str(temp_summary_structure.parent))

    summary_report = temp_summary_structure / GroupSummaryConstants.SUMMARY_REPORT

    assert (
        summary_report.exists()
    ), f"Summary report should have been created containing all test cases with computed values."

    full_summary_csv_dict = csv.DictReader(open(full_summary_csv))
    missing_csv_file_dict = csv.DictReader(open(missing_csv_file))
    summary_report_dict = csv.DictReader(open(summary_report))

    report_names = {s["Dataset"] for s in summary_report_dict}
    missed_names = {r["dataset_name"] for r in missing_csv_file_dict}
    full_summ_names = {r["dataset_name"] for r in full_summary_csv_dict}
    all_summ_names = missed_names.union(full_summ_names)
    set_diff = report_names - all_summ_names
    assert (
        len(set_diff) == 1
    ), "Summary Report should contain the collection of all summaries csvs (merged) + a new Summary Average Row."


def test_failed_test_cases(
    temp_summary_structure: Path,
) -> None:
    """Test to see the list of test case paths that failed are outputted into a new file for
    retries."""

    missing_csv_file = temp_summary_structure / GroupSummaryConstants.MISSING_SUMMARIES_CSV
    missing_csv_file_dict = csv.DictReader(open(missing_csv_file))

    failed_test_cases_file = (
        temp_summary_structure / GroupSummaryConstants.FAILED_TEST_CASE_PATHS_YAML
    )
    failed_test_cases_data = yaml.safe_load(open(failed_test_cases_file))

    missing_dataset_names = {r["dataset_name"] for r in missing_csv_file_dict}
    failed_test_case_names = {
        Path(test_case_path).with_suffix("").name
        for test_case_path in failed_test_cases_data["test_paths"]
    }

    missing_set_diff = missing_dataset_names - failed_test_case_names
    failed_test_cases_set_diff = failed_test_case_names - missing_dataset_names

    assert (
        not missing_set_diff
    ), "Missing dataset should map 1:1 to a test case path in the failed test cases file."
    assert (
        not failed_test_cases_set_diff
    ), "Failed test case paths should map 1:1 to a missing dataset in the missing summary csv file."


def test_missing_summary_serialization(
    temp_summary_structure: Path,
) -> None:
    """Test to see that the missing summary csv serializations works as expected."""

    missing_csv_file = temp_summary_structure / GroupSummaryConstants.MISSING_SUMMARIES_CSV
    missing_csv_file_dict = csv.DictReader(open(missing_csv_file))

    # We can dump the values into the metric object constructor.
    #   If serialization breaks the data, then this constructor will raise a pydantic dataclass exc.

    for csv_row in missing_csv_file_dict:
        ToolCallAndRoutingMetrics(**csv_row)


def test_added_agent_to_full_summary(
    temp_summary_structure: Path,
) -> None:
    """
    Test to see if the agent column as been added to the beginning of the summary row.

    Because the dictionaries are unordered, they are ordered by insertion time. So to add a row to
    the first column, we will have to convert each row to a list the insert as the first element,
    then convert back to a dictionary object.
    """

    full_summary_csv = temp_summary_structure / GroupSummaryConstants.SUMMARIES_CSV
    full_summary_data = csv.DictReader(open(full_summary_csv))
    header_row = list(list(full_summary_data)[0].keys())
    header_len = len(header_row)
    assert (
        header_row[0] == "agent"
    ), "Header row should have a new entry in the first column: `agent`"
    assert all(
        header_len == len(row) for row in full_summary_data
    ), "All data rows should have the same length as the header."
