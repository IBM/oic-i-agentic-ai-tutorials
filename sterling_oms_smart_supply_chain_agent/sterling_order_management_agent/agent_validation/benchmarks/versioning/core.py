import json
import os
from pathlib import Path
import sys
from typing import List, Optional, Set

from agent_validation.benchmarks.versioning.models import DomainRequest, DomainScanResult
import numpy as np
import pandas as pd


def find_domain_roots_by_name(test_dir: Path, domain_name: str) -> List[Path]:
    """
    Recursively search test_dir for directories named exactly domain_name.

    Returns a deduped, shallowest-first list of Paths.
    """
    if not test_dir.exists() or not test_dir.is_dir():
        raise FileNotFoundError(f"test_dir not found or not a directory: {test_dir}")

    target = domain_name.strip().lower()
    matches: Set[Path] = set()
    for p in test_dir.rglob("*"):
        try:
            if p.is_dir() and p.name.lower() == target:
                matches.add(p)
        except PermissionError:
            continue

    return sorted(matches, key=lambda x: (len(x.relative_to(test_dir).parts), str(x)))


def load_manager_agent_name(test_file_path: Path) -> Optional[str]:
    """
    Safely loads a JSON file and returns the 'agent' name.

    Args:
        test_file_path: The filesystem Path to the test case JSON file.

    Returns:
        The agent name as a string, or None
    """
    try:
        with open(test_file_path, "r", encoding="utf-8") as f:

            data = json.load(f)
            if data["agent"] is not None:
                return str(data["agent"])
        return None

    except (FileNotFoundError, json.JSONDecodeError, IOError, PermissionError) as e:
        print(
            f"Warning: Could not load agent from {test_file_path}. Error: {e}",
            file=sys.stderr,
        )
        return None


def scan_domain_details(req: DomainRequest) -> List[DomainScanResult]:
    """
    Finds all domain roots and scans them for unique dataset files.
    Args:
        req (DomainRequest): The domain scanning configuration including the
            root test directory, domain name to search for, file glob pattern.


    Returns:
        List of DomainScanResult: An object containing the matched domain name,
        a list of root directories where it was found, and the dataset names.
    """
    roots = find_domain_roots_by_name(req.test_dir, req.domain_name)
    if not roots:
        raise FileNotFoundError(
            f"No directory named '{req.domain_name}' found under {req.test_dir}"
        )

    results_list: List[DomainScanResult] = []
    for root in roots:
        for path in root.rglob(req.dataset_glob):
            if not path.is_file():
                continue

            result = DomainScanResult(
                domain_name=req.domain_name,
                dataset_name=path.stem.strip(),
                agent=load_manager_agent_name(path),
                file_path=str(path),
            )
            results_list.append(result)

    return results_list


def convert_results_to_dataframe(results_list: List[DomainScanResult]) -> pd.DataFrame:
    """Converts the list of dataclasses to a DataFrame."""
    if not results_list:
        return pd.DataFrame(columns=["domain_name", "agent", "dataset_name", "file_path"])

    return pd.DataFrame(results_list)


def scan_master_list(
    test_dir: Path,
    dataset_glob: str,
    case_insensitive: bool,
    domain_list: Optional[List[str]] = None,
) -> List[DomainScanResult]:
    """
    Scans for all required tests.

    - If domain_list is provided, scans only those domains.
    - If domain_list is empty, scans all subdirectories in `test_dir`.
    """
    all_scan_results: List[DomainScanResult] = []
    domains_to_scan: Set[str] = set()

    if domain_list:
        domains_to_scan.update(domain_list)
        print(f"Scanning specified domains: {domain_list}", file=sys.stderr)
    else:
        print(f"No domains specified, scanning all in {test_dir}...", file=sys.stderr)
        try:
            for item in test_dir.iterdir():
                if item.is_dir():
                    domains_to_scan.add(item.name)
        except FileNotFoundError:
            print(f"Test directory not found: {test_dir}", file=sys.stderr)

    # Now, run the scan for each domain
    for domain_name in domains_to_scan:
        req = DomainRequest(
            test_dir=test_dir,
            domain_name=domain_name,
            dataset_glob=dataset_glob,
            case_insensitive=case_insensitive,
        )
        all_scan_results.extend(scan_domain_details(req))

    return all_scan_results


def save_dataframe_to_csv(df: pd.DataFrame, output_dir: Optional[Path], filename: str) -> None:
    """Saves a DataFrame to a CSV file in the specified directory."""
    if not output_dir:
        return
    try:
        output_path = os.path.join(output_dir, filename)
        output_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, float_format="%.3f")
        print(f" -> Wrote {filename} to: {output_path}")
    except OSError as e:
        print(f"Could not write file '{filename}' to '{output_dir}': {e}", file=sys.stderr)


def print_summary_grouping(df: pd.DataFrame, output_dir: Optional[Path] = None) -> None:
    """Displays the grouping of domains and agents."""

    if df.empty:
        print("--- Summary ---")
        print("No matching results to summarize.")
        return

    total_runs = len(df)
    if total_runs == 0:
        return

    # convert text match to bool
    df["text_match_bool"] = df["text_match"] == "Summary Matched"
    # calculate precision
    df["tool_precision"] = df["correct_tool_calls"] / df["total_tool_calls"]
    # calculate recall
    df["tool_recall"] = df["correct_tool_calls"] / df["expected_tool_calls"]
    # display results

    summary = df.groupby(["domain_name", "agent"], as_index=False).agg(
        {
            "total_steps": "mean",
            "llm_step": "mean",
            "tool_precision": "mean",
            "tool_recall": "mean",
            "is_success": "mean",
            "text_match_bool": "mean",
        }
    )

    print("\n--- Summary Grouping ---")
    print(summary.to_string())
    if output_dir:

        save_dataframe_to_csv(summary, output_dir, "detailed_grouping_summary.csv")
    return


def add_detailed_metric_columns(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    Takes a DataFrame and adds calculated metric columns (tool_precision, tool_recall,
    text_match_bool).

    Returns the modified DataFrame or None if required columns are missing.
    """
    if df.empty:
        return None

    required_cols = [
        "domain_name",
        "agent",
        "text_match",
        "correct_tool_calls",
        "total_tool_calls",
        "expected_tool_calls",
        "total_steps",
        "llm_step",
        "is_success",
    ]

    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Cannot generate detailed metrics. Missing columns: {missing_cols}", file=sys.stderr)
        return None

    df_copy = df.copy()

    # convert text match to bool
    df_copy["text_match_bool"] = df_copy["text_match"].str.strip().str.lower() == "summary matched"

    # calculate precision
    df_copy["tool_precision"] = np.where(
        df_copy["total_tool_calls"] > 0,
        df_copy["correct_tool_calls"] / df_copy["total_tool_calls"],
        0,
    )
    # calculate recall
    df_copy["tool_recall"] = np.where(
        df_copy["expected_tool_calls"] > 0,
        df_copy["correct_tool_calls"] / df_copy["expected_tool_calls"],
        0,
    )
    # Ensure is_success is a boolean/float for aggregation
    df_copy["is_success"] = df_copy["is_success"].astype(bool)

    return df_copy


def print_ranking_report(
    df: pd.DataFrame,
    categories_to_rank: List[str],
    min_evals: int = 5,
    rank_by: Optional[str] = None,
    sort_order: str = "desc",
    output_dir: Optional[Path] = None,
) -> None:
    """Analyzes filtered data using detailed metric calculations and prints simple rank tables for
    each metric."""
    if df.empty:
        print("\n--- Performance Rankings ---")
        print("No data to rank after filtering.")
        return

    print("\n--- Performance Rankings ---")

    # Get the detailed metrics DataFrame
    detailed_df = add_detailed_metric_columns(df)

    if detailed_df is None:
        print(
            f"\nSkipping Performance Rankings: Missing columns required for detailed metrics.",
            file=sys.stderr,
        )

        return

    # Define metrics to rank based on user request
    metrics_to_rank = {
        "is_success": True,
        "text_match_bool": True,
        "tool_precision": True,
        "tool_recall": True,
        "total_steps": False,
        "llm_step": False,
    }

    if rank_by:
        if rank_by in metrics_to_rank:
            metrics_to_rank = {rank_by: metrics_to_rank[rank_by]}
        else:
            print(f"Metric '{rank_by}' not found. Showing all metrics.", file=sys.stderr)
            print(f"Available metrics: {list(metrics_to_rank.keys())}", file=sys.stderr)

    for category_col in categories_to_rank:
        if category_col not in detailed_df.columns:
            print(f"\nSkipping category '{category_col}': not found in data.", file=sys.stderr)
            continue

        print(f"\n{'-'*10} Rankings by: '{category_col}' {'-'*10}")

        # Aggregate the detailed metrics by the category
        agg_dict = {"test_runs": (category_col, "size")}
        for metric in metrics_to_rank:
            agg_dict[metric] = (metric, "mean")  # All rankings are based on the mean

        try:
            summary_df = detailed_df.groupby(category_col).agg(**agg_dict).reset_index()
        except ValueError as e:
            print(f"Error during groupby-agg for '{category_col}': {e}", file=sys.stderr)
            continue

        # Filter by min_evals
        filtered_summary_df = summary_df[summary_df["test_runs"] >= min_evals]

        if filtered_summary_df.empty:
            print(f"  (No groups met the minimum eval count of {min_evals})")
            continue

        print(f" (Filtered groups with < {min_evals} evals)")

        # Loop through each metric and print the simple rank table
        for metric_col in list(metrics_to_rank.keys()):

            if metric_col not in metrics_to_rank:
                continue

            # Determine sort order
            if sort_order.lower() == "desc":
                ascending_order = False
            else:
                ascending_order = True  # Default to 'asc'

            metric_table = filtered_summary_df[[category_col, metric_col, "test_runs"]].copy()
            metric_table = metric_table.sort_values(by=metric_col, ascending=ascending_order)
            metric_table["rank"] = range(1, len(metric_table) + 1)
            metric_table = metric_table[["rank", category_col, metric_col, "test_runs"]]

            print(f"\n# {metric_col} (sort: {sort_order})\n")
            with pd.option_context(
                "display.max_columns",
                None,
                "display.width",
                160,
                "display.float_format",
                "{:,.3f}".format,
            ):
                print(metric_table.to_string(index=False))
            try:
                if output_dir is not None:
                    output_name = f"{category_col}_ranking_report_by_{metric_col}.csv"
                    output_path = os.path.join(output_dir, output_name)

                    output_dir.mkdir(parents=True, exist_ok=True)

                    metric_table.to_csv(output_path, index=False, float_format="%.3f")
            except OSError as e:
                print(f"Could not write ranking report to file: {e}", file=sys.stderr)
            print("-" * 40)
