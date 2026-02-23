"""
Unit tests for mock_generator module.

Tests the functionality of generating mock files from tool call results.
"""

import json
from pathlib import Path
import tempfile

from agent_validation.util.mock_generator import (
    ToolCallConfig,
    _collect_pydantic_classes,
    _format_value_repr,
    _generate_mock_code,
    _get_computed_field_names,
    _load_config,
)
from pydantic import BaseModel, ValidationError
import pytest


# Test fixtures and models
class SimpleModel(BaseModel):
    """Simple Pydantic model for testing."""

    name: str
    value: int


class NestedModel(BaseModel):
    """Nested Pydantic model for testing."""

    simple: SimpleModel
    items: list[str]


class TestLoadConfig:
    """Tests for _load_config function."""

    def test_load_yaml_config(self) -> None:
        """Test loading a YAML config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("tool_name: test_tool\n")
            f.write("tool_args:\n")
            f.write("  arg1: value1\n")
            f.write("  arg2: 123\n")
            temp_path = f.name

        try:
            config = _load_config(Path(temp_path))
            assert config.tool_name == "test_tool"
            assert config.tool_args == {"arg1": "value1", "arg2": 123}
        finally:
            Path(temp_path).unlink()

    def test_load_json_config(self) -> None:
        """Test loading a JSON config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"tool_name": "test_tool", "tool_args": {"arg1": "value1"}}, f)
            temp_path = f.name

        try:
            config = _load_config(Path(temp_path))
            assert config.tool_name == "test_tool"
            assert config.tool_args == {"arg1": "value1"}
        finally:
            Path(temp_path).unlink()

    def test_load_config_file_not_found(self) -> None:
        """Test loading a non-existent config file."""
        with pytest.raises(FileNotFoundError):
            _load_config(Path("/nonexistent/path.yaml"))

    def test_load_config_unsupported_format(self) -> None:
        """Test loading a config file with unsupported format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("some content")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Unsupported config file format"):
                _load_config(Path(temp_path))
        finally:
            Path(temp_path).unlink()


class TestGetComputedFieldNames:
    """Tests for _get_computed_field_names function."""

    def test_simple_model_no_computed_fields(self) -> None:
        """Test model with no computed fields."""
        model = SimpleModel(name="test", value=42)
        computed = _get_computed_field_names(model)
        assert computed == set()

    def test_tool_response_has_is_success(self) -> None:
        """Test that ToolResponse always has is_success as computed field."""

        # Create a mock ToolResponse-like object using a real class
        class MockToolResponse:
            def __init__(self):
                self.error_details = None
                self.tool_output = "result"

        MockToolResponse.__name__ = "ToolResponse"
        mock_response = MockToolResponse()

        computed = _get_computed_field_names(mock_response)
        assert "is_success" in computed


class TestFormatValueRepr:
    """Tests for _format_value_repr function."""

    def test_format_none(self) -> None:
        """Test formatting None value."""
        assert _format_value_repr(None) == "None"

    def test_format_string(self) -> None:
        """Test formatting string value."""
        assert _format_value_repr("hello") == '"hello"'

    def test_format_int(self) -> None:
        """Test formatting integer value."""
        assert _format_value_repr(42) == "42"

    def test_format_float(self) -> None:
        """Test formatting float value."""
        assert _format_value_repr(3.14) == "3.14"

    def test_format_bool(self) -> None:
        """Test formatting boolean value."""
        assert _format_value_repr(True) == "True"
        assert _format_value_repr(False) == "False"

    def test_format_empty_list(self) -> None:
        """Test formatting empty list."""
        assert _format_value_repr([]) == "[]"

    def test_format_simple_list(self) -> None:
        """Test formatting simple list."""
        result = _format_value_repr([1, 2, 3])
        assert "[" in result
        assert "1" in result
        assert "2" in result
        assert "3" in result

    def test_format_empty_dict(self) -> None:
        """Test formatting empty dict."""
        assert _format_value_repr({}) == "{}"

    def test_format_simple_dict(self) -> None:
        """Test formatting simple dict."""
        result = _format_value_repr({"key": "value"})
        assert "{" in result
        assert '"key"' in result
        assert '"value"' in result

    def test_format_pydantic_model(self) -> None:
        """Test formatting Pydantic model."""
        model = SimpleModel(name="test", value=42)
        result = _format_value_repr(model)
        assert "SimpleModel(" in result
        assert 'name="test"' in result
        assert "value=42" in result

    def test_format_nested_pydantic_model(self) -> None:
        """Test formatting nested Pydantic model."""
        nested = NestedModel(simple=SimpleModel(name="inner", value=10), items=["a", "b"])
        result = _format_value_repr(nested)
        assert "NestedModel(" in result
        assert "SimpleModel(" in result
        assert 'name="inner"' in result


class TestCollectPydanticClasses:
    """Tests for _collect_pydantic_classes function."""

    def test_collect_simple_model(self) -> None:
        """Test collecting classes from simple model."""
        model = SimpleModel(name="test", value=42)
        classes = _collect_pydantic_classes(model)
        assert SimpleModel in classes

    def test_collect_nested_model(self) -> None:
        """Test collecting classes from nested model."""
        nested = NestedModel(simple=SimpleModel(name="inner", value=10), items=["a", "b"])
        classes = _collect_pydantic_classes(nested)
        assert NestedModel in classes
        assert SimpleModel in classes

    def test_collect_from_list(self) -> None:
        """Test collecting classes from list of models."""
        models = [
            SimpleModel(name="first", value=1),
            SimpleModel(name="second", value=2),
        ]
        classes = _collect_pydantic_classes(models)
        assert SimpleModel in classes

    def test_collect_from_dict(self) -> None:
        """Test collecting classes from dict containing models."""
        data = {"model": SimpleModel(name="test", value=42)}
        classes = _collect_pydantic_classes(data)
        assert SimpleModel in classes

    def test_collect_from_primitive(self) -> None:
        """Test collecting classes from primitive value."""
        classes = _collect_pydantic_classes(42)
        assert len(classes) == 0


class TestGenerateMockCode:
    """Tests for _generate_mock_code function."""

    def test_generate_basic_mock(self) -> None:
        """Test generating basic mock code."""
        result = SimpleModel(name="test", value=42)
        code = _generate_mock_code(
            tool_name="test_tool",
            tool_args={"arg1": "value1"},
            result=result,
            tool_module_path="test.module",
        )

        # Check imports
        assert "from typing import Any" in code
        assert "from agent_ready_tools.utils.tool_snapshot.patch import patch_tool_id" in code

        # Check decorator
        assert '@patch_tool_id(tool_name="test_tool"' in code
        assert 'tool_kwargs={"arg1": "value1"}' in code

        # Check function
        assert "def fixture_test_tool(*args: Any, **kwargs: Any)" in code
        assert "return SimpleModel(" in code

    def test_generate_mock_no_args(self) -> None:
        """Test generating mock code with no tool arguments."""
        result = SimpleModel(name="test", value=42)
        code = _generate_mock_code(
            tool_name="test_tool",
            tool_args={},
            result=result,
            tool_module_path="test.module",
        )

        # Should not have tool_kwargs in decorator
        assert "tool_kwargs" not in code
        assert '@patch_tool_id(tool_name="test_tool")' in code

    def test_generate_mock_with_tool_response(self) -> None:
        """Test generating mock code for ToolResponse type."""
        # Create a mock ToolResponse using a real class
        mock_output = SimpleModel(name="output", value=100)

        class MockToolResponse:
            def __init__(self) -> None:
                self.error_details = None
                self.tool_output = mock_output

        MockToolResponse.__name__ = "ToolResponse"
        mock_response = MockToolResponse()

        code = _generate_mock_code(
            tool_name="test_tool",
            tool_args={},
            result=mock_response,
            tool_module_path="test.module",
        )

        # Check return type includes generic parameter
        assert "-> ToolResponse[SimpleModel]:" in code

    def test_generate_mock_function_name(self) -> None:
        """Test that function name is correctly generated."""
        result = SimpleModel(name="test", value=42)
        code = _generate_mock_code(
            tool_name="my_custom_tool",
            tool_args={},
            result=result,
        )

        assert "def fixture_my_custom_tool(" in code

    def test_generate_mock_with_nested_model(self) -> None:
        """Test generating mock code with nested Pydantic models."""
        nested = NestedModel(simple=SimpleModel(name="inner", value=10), items=["a", "b"])
        code = _generate_mock_code(
            tool_name="test_tool",
            tool_args={},
            result=nested,
            tool_module_path="test.module",
        )

        # Should import both models
        assert "NestedModel" in code
        assert "SimpleModel" in code


class TestToolCallConfig:
    """Tests for ToolCallConfig model."""

    def test_valid_config(self) -> None:
        """Test creating valid ToolCallConfig."""
        config = ToolCallConfig(tool_name="test_tool", tool_args={"arg1": "value1"})
        assert config.tool_name == "test_tool"
        assert config.tool_args == {"arg1": "value1"}

    def test_config_validation(self) -> None:
        """Test ToolCallConfig validation."""

        with pytest.raises(ValidationError):  # Pydantic validation error
            ToolCallConfig(tool_name="test_tool")  # type: ignore  # Missing tool_args


class TestIntegration:
    """Integration tests for the mock generator."""

    def test_end_to_end_yaml_to_mock(self) -> None:
        """Test complete flow from YAML config to mock code generation."""
        # Create a temporary YAML config
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("tool_name: test_tool\n")
            f.write("tool_args:\n")
            f.write("  param1: value1\n")
            temp_path = f.name

        try:
            # Load config
            config = _load_config(Path(temp_path))
            assert config.tool_name == "test_tool"
            assert config.tool_args == {"param1": "value1"}

            # Generate mock code (with mock result)
            result = SimpleModel(name="result", value=123)
            code = _generate_mock_code(
                tool_name=config.tool_name,
                tool_args=config.tool_args,
                result=result,
            )

            # Verify generated code structure
            assert "fixture_test_tool" in code
            assert "param1" in code
            assert "value1" in code
        finally:
            Path(temp_path).unlink()

    def test_format_and_collect_consistency(self) -> None:
        """Test that _format_value_repr and _collect_pydantic_classes work together."""
        nested = NestedModel(simple=SimpleModel(name="test", value=42), items=["x", "y"])

        # Format the value
        formatted = _format_value_repr(nested)

        # Collect classes
        classes = _collect_pydantic_classes(nested)

        # Both should recognize the nested structure
        assert "NestedModel" in formatted
        assert "SimpleModel" in formatted
        assert NestedModel in classes
        assert SimpleModel in classes


# Made with Bob
