python_sources()

resource(
    name = "default_benchmarks_config",
    source = "benchmarks_config.yaml",
)

python_tests(
    name = "tests",
    overrides = {
        "test_validate_adk_test_cases.py": {
            "dependencies": [
                "agent_validation/adk_test_cases:adk_test_cases",
                ":default_benchmarks_config",
            ],
        },
    },
)
