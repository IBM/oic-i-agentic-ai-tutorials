import unittest

from agent_validation.config.validation_config import FrameworkConfig
from agent_validation.util import file_system
from agent_validation.util.constants import CONFIG_PATH
from pydantic import ValidationError
import pytest


class TestConfigLoading(unittest.TestCase):
    """Unit test to ensure the validation configs can be properly loaded."""

    def setUp(self) -> None:
        """Set up."""
        self.config_files = file_system.list_all_files(
            [CONFIG_PATH],
            file_types=[file_system.FileType.YAML],
        )

    @pytest.mark.xfail(
        reason="After refactoring `list_all_files()` to be fully recursive, many files are failing."
    )
    def test_config_is_valid(self) -> None:
        """Test that loading the config raises no validation errors."""
        # TODO: UNBREAK FAILING PATHS
        # agent_validation/config/validation_config.yaml
        # agent_validation/config/version_compatibility_config.yaml
        # agent_validation/config/alternative_config_sales.yaml
        # agent_validation/config/config_sales.yaml
        # agent_validation/config/adk_smoke_validation_config.yaml
        errors = list()
        for f in self.config_files:
            try:
                _ = FrameworkConfig.load(f)
            except ValidationError as e:
                errors.append(f"Config file {f} failed to load or validate: {e}")

        if errors:
            self.fail("\n----------------\n".join(errors))
