from pathlib import Path

OUTPUT_DIRECTORY: str = "agent_validation/benchmarks/results"
ADK_TEST_CASES_DIR: str = "agent_validation/adk_test_cases"
ADK_TEST_CASES_DIR_PATH: Path = Path(ADK_TEST_CASES_DIR)
# Default CSV column name for dataset matching
DEFAULT_DATASET_COL: str = "dataset_name"

# Default glob pattern for finding test files
DEFAULT_DATASET_GLOB: str = "*.json"
SUMMARY_METRICS: str = "summary_metrics.csv"
