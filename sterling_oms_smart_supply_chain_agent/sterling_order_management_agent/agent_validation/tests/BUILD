python_tests(
    name = "tests",
    overrides = {
        "config_test.py": {
            "dependencies": ["agent_validation:configs"],
        },
    },
)

resources(
    name = "test_data",
    sources = [
        "test_data/**",
    ],
)
