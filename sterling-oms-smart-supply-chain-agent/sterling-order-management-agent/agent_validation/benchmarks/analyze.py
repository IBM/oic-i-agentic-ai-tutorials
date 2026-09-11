import pathlib
import sys
from typing import Optional, Tuple

from agent_validation.benchmarks.versioning import eval_constants as ec
from agent_validation.benchmarks.versioning.core import (
    convert_results_to_dataframe,
    print_ranking_report,
    print_summary_grouping,
    scan_master_list,
)
from agent_validation.benchmarks.versioning.lib import BenchmarkDirectory
import pandas as pd
import typer

app = typer.Typer()


def load_and_filter_data(
    benchmark_dir: pathlib.Path,
    domain: Optional[str],
    agent: Optional[str],
) -> Optional[Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Common logic to load, scan, merge, and filter data.

    Returns a tuple of (filtered_dataframe, main_original_dataframe) or None.
    """
    test_dir = ec.ADK_TEST_CASES_DIR_PATH
    dataset_col = ec.DEFAULT_DATASET_COL
    ci = True

    domain_list = [d.strip() for d in domain.split(",") if d.strip()] if domain else None
    agent_list = [a.strip() for a in agent.split(",") if a.strip()] if agent else None

    # Scan Test Files
    scan_results = scan_master_list(
        test_dir=test_dir,
        dataset_glob=ec.DEFAULT_DATASET_GLOB,
        case_insensitive=ci,
        domain_list=domain_list,
    )
    if not scan_results:
        print(f"No test files found in '{test_dir}'.", file=sys.stderr)
        return None

    scan_df = convert_results_to_dataframe(scan_results)

    # Load Main CSV
    try:
        benchmark = BenchmarkDirectory.load_from_path(versioned_dir_path=benchmark_dir)
    except FileNotFoundError as e:
        print(f"loading benchmark directory '{benchmark_dir}': {e}", file=sys.stderr)
        return None

    main_df: pd.DataFrame = pd.DataFrame()
    if benchmark.benchmark_results_summary:
        main_df = benchmark.benchmark_results_summary.dataframe

    if main_df.empty:
        print(f"No summary dataframe found in '{benchmark_dir}'.", file=sys.stderr)
        return None

    total_rows = main_df.shape[0]
    if dataset_col not in main_df.columns:
        print(
            f"Column '{dataset_col}' not in CSV. Available: {list(main_df.columns)}",
            file=sys.stderr,
        )
        return None

    # Join CSV and Scan Data
    main_df_copy = main_df.copy()
    scan_df_copy = scan_df.copy()

    # Prioritize scan_df for metadata.
    common_metadata = (set(main_df_copy.columns) & set(scan_df_copy.columns)) - {dataset_col}
    if common_metadata:
        main_df_copy = main_df_copy.drop(columns=list(common_metadata))

    merged_df = pd.merge(main_df_copy, scan_df_copy, on=dataset_col, how="inner")

    # Filter Merged Results
    filtered_df = merged_df.copy()

    if domain_list:
        if "domain_name" not in filtered_df.columns:
            print(
                f"Error: 'domain_name' column not found after merge. Cannot filter by domain.",
                file=sys.stderr,
            )
            return None
        filtered_df = filtered_df[filtered_df["domain_name"].isin(domain_list)]

    if agent_list:
        if "agent" not in filtered_df.columns:
            print(
                f"Error: 'agent' column not found after merge. Cannot filter by agent.",
                file=sys.stderr,
            )
            return None
        filtered_df = filtered_df[filtered_df["agent"].isin(agent_list)]

    # Print Filter Results
    kept = len(filtered_df)
    print(f"\n--- Filter Results ---")
    print(f"Kept {kept}/{total_rows} rows from '{ec.SUMMARY_METRICS}'.")
    if agent_list:
        print(f"Filtered by agent(s): {agent_list}")
    if domain_list:
        print(f"Filtered by domain(s): {domain_list}")

    return filtered_df, main_df


@app.command(name="group-results")
def group_results(
    benchmark_dir: pathlib.Path = typer.Option(
        ...,
        "--benchmark-dir",
        help="Path to the *versioned* benchmark directory (e.g., .../2025-11-04T...Z).",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    domain: Optional[str] = typer.Option(
        None,
        "--domain",
        help="Comma-separated list of domain names. (Scans all if not set). Example: --domain hr,procurement",
    ),
    agent: Optional[str] = typer.Option(
        None,
        "--agent",
        help="Comma-separated list of agent names. Example: --domain sap_employee_support_manager,workday_employee_support_manager",
    ),
    output_dir: Optional[pathlib.Path] = typer.Option(
        None,
        "--output-dir",
        help="Directory to write the filtered CSV file (optional).",
        writable=True,
    ),
) -> None:
    """
    Filter a summary CSV by discovered tests matching agent or domain.

    This tool joins CSV data with file system scan data and allows filtering and summarizing on the
    combined results.
    """

    preview_rows = 60
    output_name = "filtered_report.csv"

    load_result = load_and_filter_data(benchmark_dir=benchmark_dir, domain=domain, agent=agent)

    if load_result is None:
        print("Failed to load or filter data.")
        return

    filtered_df, main_df = load_result

    if filtered_df is None or filtered_df.empty:
        if filtered_df is not None:
            print("No rows matched all filters.")
        return

    if output_dir:
        try:

            original_cols_wanted = list(main_df.columns)

            available_cols = [col for col in original_cols_wanted if col in filtered_df.columns]
            for col in ["domain_name", "agent"]:
                if col not in available_cols and col in filtered_df.columns:
                    available_cols.insert(1, col)
            available_cols = list(dict.fromkeys(available_cols))

            final_csv_df = filtered_df.loc[:, available_cols].drop_duplicates()
            kept = len(final_csv_df)

            output_path = output_dir / output_name
            output_dir.mkdir(parents=True, exist_ok=True)
            final_csv_df.to_csv(output_path, index=False)
            print(f"Wrote {kept} filtered rows to: {output_path}")
        except OSError as e:
            print(f"Could not write filtered rows file '{output_path}': {e}", file=sys.stderr)

    if not output_dir:
        # Print to terminal
        kept = len(filtered_df)
        if kept > 0 and preview_rows > 0:
            print("\n--- Filtered CSV Rows ---")
            with pd.option_context("display.max_columns", None, "display.width", 160):
                print(filtered_df.head(preview_rows).to_string(index=False))
                if kept > preview_rows:
                    print(f"... ({kept - preview_rows} more rows)")
        elif kept == 0:
            print("No rows matched all filters.")

    # Display Grouping Summary
    print_summary_grouping(filtered_df, output_dir=output_dir)


@app.command(name="rank-agents")
def rank_agents(
    benchmark_dir: pathlib.Path = typer.Option(
        ...,
        "--benchmark-dir",
        help="Path to the *versioned* benchmark directory.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    domain: Optional[str] = typer.Option(None, "--domain", help="Filter by domain(s)."),
    agent: Optional[str] = typer.Option(None, "--agent", help="Filter by agent(s)."),
    output_dir: Optional[pathlib.Path] = typer.Option(
        None, "--output-dir", help="Directory to write ranking CSVs.", writable=True
    ),
    min_evals: int = typer.Option(5, "--min-evals", help="Minimum evals to be ranked."),
    rank_by: Optional[str] = typer.Option(
        None, "--rank-by", help="Metric to rank by (e.g., 'tool_precision')."
    ),
    sort_order: str = typer.Option("desc", "--sort-by", help="Sort by: 'asc' or 'desc'."),
) -> None:
    """Filters results and ranks AGENTS by performance metrics."""

    load_result = load_and_filter_data(benchmark_dir=benchmark_dir, domain=domain, agent=agent)

    if load_result is None:
        print("Failed to load or filter data.")
        return

    filtered_df, _ = load_result

    if filtered_df is None or filtered_df.empty:
        print("No data to rank.")
        return

    print_ranking_report(
        df=filtered_df,
        categories_to_rank=["agent"],
        min_evals=min_evals,
        rank_by=rank_by,
        sort_order=sort_order,
        output_dir=output_dir,
    )


@app.command(name="rank-domains")
def rank_domains(
    benchmark_dir: pathlib.Path = typer.Option(
        ...,
        "--benchmark-dir",
        help="Path to the *versioned* benchmark directory.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    domain: Optional[str] = typer.Option(None, "--domain", help="Filter by domain(s)."),
    agent: Optional[str] = typer.Option(None, "--agent", help="Filter by agent(s)."),
    output_dir: Optional[pathlib.Path] = typer.Option(
        None, "--output-dir", help="Directory to write ranking CSVs.", writable=True
    ),
    min_evals: int = typer.Option(5, "--min-evals", help="Minimum evals to be ranked."),
    rank_by: Optional[str] = typer.Option(
        None, "--rank-by", help="Metric to rank by (e.g., 'tool_precision')."
    ),
    sort_order: str = typer.Option("desc", "--sort-by", help="Sort by: 'asc' or 'desc'."),
) -> None:
    """Filters results and ranks DOMAINS and DOMAIN-AGENT PAIRS by performance metrics."""

    load_result = load_and_filter_data(benchmark_dir=benchmark_dir, domain=domain, agent=agent)

    if load_result is None:
        print("Failed to load or filter data.")
        return

    filtered_df, _ = load_result

    if filtered_df is None or filtered_df.empty:
        print("No data to rank.")
        return

    # Create a composite column for combined ranking
    if "domain_name" in filtered_df.columns and "agent" in filtered_df.columns:
        filtered_df["domain_agent_pair"] = (
            filtered_df["domain_name"].astype(str) + " / " + filtered_df["agent"].astype(str)
        )

    # Define categories to rank for this command
    categories_to_rank = ["domain_name", "domain_agent_pair"]

    print_ranking_report(
        df=filtered_df,
        categories_to_rank=categories_to_rank,
        min_evals=min_evals,
        rank_by=rank_by,
        sort_order=sort_order,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    app()
