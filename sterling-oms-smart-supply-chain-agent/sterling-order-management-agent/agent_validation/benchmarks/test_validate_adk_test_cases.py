from pathlib import Path

from agent_validation.benchmarks.run import (
    ADK_TEST_CASES_DIR,
    get_all_test_cases,
    get_test_cases_from_config,
    validate_test_case_paths,
)


def test_validate_all_test_case_paths_uniqueness() -> None:
    """Validation test to confirm test case file names are unique."""
    assert (
        ADK_TEST_CASES_DIR.exists() and ADK_TEST_CASES_DIR.is_dir()
    ), "ADK_TEST_CASES_DIR not available."
    cases = get_all_test_cases(ADK_TEST_CASES_DIR)
    validate_test_case_paths(cases)


def test_validate_default_config_test_paths() -> None:
    """Validate the test case path string representations in the config."""
    benchmarks_yaml = Path("agent_validation/benchmarks/benchmarks_config.yaml")
    assert benchmarks_yaml.exists(), "benchmarks_config.yaml does not exist"
    test_cases = get_test_cases_from_config(benchmarks_yaml)
    validate_test_case_paths(test_cases)
