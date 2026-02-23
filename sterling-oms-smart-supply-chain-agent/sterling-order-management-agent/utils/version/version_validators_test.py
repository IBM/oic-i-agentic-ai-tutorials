# Assisted by watsonx Code Assistant


import pytest
from utils.version.version_validators import is_valid_version


def test_is_valid_version() -> None:
    """Test `is_valid_version`."""
    valid_versions = [
        "1.3.2",
        "2.3.2-beta",
        "3.0.0-rc.1",
        "1.0.0",
    ]
    invalid_versions = [
        "1..2",  # Invalid due to double dot
        "1.3",  # Missing third part
        "1.3.2.4",  # More than three parts
        "latest",  # Not a version string
        "1.3.x",  # Invalid wildcard
    ]

    for version in valid_versions:
        assert is_valid_version(version) == version

    for version in invalid_versions:
        with pytest.raises(ValueError):
            is_valid_version(version)
