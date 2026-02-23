## Test Summary Filter Tool


This command-line tool filters a main summary CSV file based on test case data (domains, agents) found by scanning the file system.

## Usage

1. Scan all domains and filter a summary_metrics.csv file, print to the terminal

This will scan every domain in adk_test_cases directory, find all matching datasets in summary_metrics.csv, and print the result.

pants run agent_validation/benchmarks/cli_filter.py --   --benchmark-dir <path to benchmark directory>

2. Filter for a specific domain, and agent and write the result to csv file

pants run agent_validation/benchmarks/cli_filter.py --   --benchmark-dir <path to benchmark summary_metrics.csv> --domain "sales" --agent sales_manager --output-dir  <path e.g /wo/evals>

3. Filter for multiple domains

pants run agent_validation/benchmarks/cli_filter.py --   --bwnchmark-dir <path to benchmark directory> --domain "sales, procurement"

## Command-Lines 

 *  --benchmark-dir             DIRECTORY  Path to the *versioned* benchmark directory (e.g., .../2025-11-04T...Z). [default: None] [required]                                             │
│    --csv-name                  TEXT       The name of the summary CSV inside the benchmark dir. [default: summary_metrics.csv]                                                            │
│    --domain                    TEXT       Comma-separated list of domain names. (Scans all if not set) [default: None]                                                                    │
│    --agent                     TEXT       Comma-separated list of agent names. [default: None]                                                                                            │
│    --output-dir                PATH       Directory to write the filtered CSV file (optional). [default: None]                                                                            │
