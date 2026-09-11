# Assisted by watsonx Code Assistant


import pathlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from utils.directory.path_validators import (
    is_valid_dir_path,
    is_valid_excel_filepath,
    is_valid_filepath,
)


def test_is_valid_dir_path() -> None:
    """Test `is_valid_dir_path`."""

    # Use the current directory of this test as a valid dir
    test_dir_as_path: pathlib.Path = pathlib.Path(__file__).parent.resolve()
    test_filepath: pathlib.Path = pathlib.Path(__file__).resolve()

    invalid_dir = "/nonexistent_directory"

    # Test valid directory
    assert is_valid_dir_path(test_dir_as_path) == test_dir_as_path

    # Test valid directory as string
    test_dir_as_string = test_dir_as_path.as_posix()
    assert is_valid_dir_path(test_dir_as_string) == test_dir_as_string

    # Test invalid directory as string
    with pytest.raises(ValueError):
        is_valid_dir_path(invalid_dir)

    # Test invalid directory as Path
    with pytest.raises(ValueError):
        is_valid_dir_path(pathlib.Path(invalid_dir))

    # Test filepath
    with pytest.raises(ValueError):
        is_valid_dir_path(test_filepath)


def test_is_valid_filepath() -> None:
    """Test `is_valid_filepath`."""

    # Use this test file as a valid file
    test_file_as_path: pathlib.Path = pathlib.Path(__file__).resolve()
    invalid_file = "/nonexistent_file.txt"

    # Test valid file as Path
    assert is_valid_filepath(test_file_as_path) == test_file_as_path

    # Test valid file as string
    test_file_as_string = test_file_as_path.as_posix()
    assert is_valid_filepath(test_file_as_string) == test_file_as_string

    # Test invalid file
    with pytest.raises(ValueError):
        is_valid_filepath(invalid_file)


@patch("utils.directory.path_validators.is_valid_filepath")
def test_is_valid_excel_filepath(mock_is_valid_filepath: MagicMock) -> None:
    """Test `is_valid_excel_filepath`."""

    # Configure the mock to return the input path
    mock_is_valid_filepath.side_effect = lambda path: path

    # Use this test file as a base for creating test paths
    test_file = Path(__file__).resolve()

    # Create test cases for different Excel extensions
    excel_suffixes = [".xlsx", ".xls", ".xlsm", ".xlsb"]

    # Test valid Excel files
    for suffix in excel_suffixes:
        excel_path = test_file.with_suffix(suffix)
        excel_path_str = excel_path.as_posix()
        assert is_valid_excel_filepath(excel_path) == excel_path
        assert is_valid_excel_filepath(excel_path_str) == excel_path_str

    # Test invalid Excel file
    with pytest.raises(ValueError):
        non_excel_file = test_file.with_suffix(".xl")
        is_valid_excel_filepath(non_excel_file)
