# Assisted by watsonx Code Assistant

import os
import tempfile
import unittest

from agent_validation.util import file_system


class TestFileUtilities(unittest.TestCase):
    """Unit tests for file utilities methods."""

    def setUp(self) -> None:
        """Create temporary files and directories for testing."""
        # Create temporary files and directories for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        subdir = os.path.join(self.temp_dir.name, "subdir")
        os.mkdir(subdir)
        self.test_files = [
            os.path.join(self.temp_dir.name, "test1.xlsx"),
            os.path.join(self.temp_dir.name, "test2.json"),
            os.path.join(subdir, "test3.yaml"),
        ]
        for file in self.test_files:
            with open(file, "w") as f:
                f.write("")

    def tearDown(self) -> None:
        """Remove temporary files and directories after testing."""
        self.temp_dir.cleanup()

    def test_is_file_type(self) -> None:
        """Test is_file_type function with valid output extension."""
        self.assertTrue(
            file_system.is_file_type(
                self.test_files[0],
                file_system.FileType.EXCEL,
            )
        )
        self.assertTrue(
            file_system.is_file_type(
                self.test_files[1],
                file_system.FileType.JSON,
            )
        )
        self.assertTrue(
            file_system.is_file_type(
                self.test_files[2],
                file_system.FileType.YAML,
            )
        )
        self.assertFalse(
            file_system.is_file_type(
                self.test_files[0],
                file_system.FileType.JSON,
            )
        )
        self.assertFalse(
            file_system.is_file_type(
                self.test_files[1],
                file_system.FileType.YAML,
            )
        )

    def test_list_all_files_with_file_types(self) -> None:
        """Test listing files with specified filetypes."""
        file_types = [file_system.FileType.EXCEL, file_system.FileType.JSON]
        expected_files = [self.test_files[0], self.test_files[1]]
        result = file_system.list_all_files(self.test_files, file_types=file_types)
        self.assertEqual(result, expected_files)

    def test_list_all_files_without_file_types(self) -> None:
        """Test listing files with no specified filetypes."""
        expected_files = [self.test_files[0], self.test_files[1], self.test_files[2]]
        result = file_system.list_all_files(self.test_files)
        self.assertEqual(result, expected_files)

    def test_list_all_files_invalid_path(self) -> None:
        """Test handling of invalid paths during file listing."""
        invalid_path = "non_existent_file.xlsx"
        with self.assertRaises(AssertionError):
            file_system.list_all_files([invalid_path])
