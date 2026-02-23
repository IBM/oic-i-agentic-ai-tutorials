import pathlib

from agent_validation.benchmarks.versioning import eval_constants as ec
from agent_validation.benchmarks.versioning import lib
import pytest
from utils import validators


# Test cases for BenchmarkVersion
def test_eval_results_version() -> None:
    """Test `BenchmarkVersion` class."""
    valid_timestamp = "2023-10-26T14:30:00"
    valid_git_hash = "abcdef1234"

    invalid_timestamp = "2023-18-26T14:30:00"
    invalid_git_hash = "abcdefg1234"

    assert validators.is_iso_format(valid_timestamp) is True
    assert validators.is_short_git_hash(valid_git_hash) is True
    assert validators.is_iso_format(invalid_timestamp) is False
    assert validators.is_short_git_hash(invalid_git_hash) is False

    assert lib.BenchmarkVersion(time_stamp=valid_timestamp, git_hash=valid_git_hash)

    with pytest.raises(ValueError):
        lib.BenchmarkVersion(time_stamp=valid_timestamp, git_hash=invalid_git_hash)

    with pytest.raises(ValueError):
        lib.BenchmarkVersion(time_stamp=invalid_timestamp, git_hash=valid_git_hash)


def test_eval_results_metadata() -> None:
    """Test `BenchmarkMetadata` class."""
    metadata = lib.BenchmarkMetadata(
        version=lib.BenchmarkVersion(time_stamp="2023-10-26T14:30:00", git_hash="abcdef1234")
    )

    assert metadata.to_json() == {
        "version": {
            "time_stamp": "2023-10-26T14:30:00",
            "git_hash": "abcdef1234",
        }
    }

    # Test deserialization from JSON string
    json_string = """
    {
        "version": {
            "time_stamp": "2023-10-26T14:30:00",
            "git_hash": "abcdef1234"
        }
    }
    """
    deserialized_metadata = lib.BenchmarkMetadata.from_json_string(json_string)
    assert deserialized_metadata.version.time_stamp == "2023-10-26T14:30:00"
    assert deserialized_metadata.version.git_hash == "abcdef1234"


def test_eval_results_directory() -> None:
    """Test `BenchmarkDirectory` class."""

    valid_timestamp = "2023-10-26T14:30:00"
    valid_git_hash = "abcdef1234"
    eval_dir = lib.BenchmarkDirectory.build(
        dir_path="/path/to/nonexistent/dir",
        version=lib.BenchmarkVersion(
            time_stamp=valid_timestamp,
            git_hash=valid_git_hash,
        ),
    )
    assert eval_dir.dir_path == pathlib.Path("/path/to/nonexistent/dir/2023-10-26T14:30:00")
    assert eval_dir.metadata.version.time_stamp == valid_timestamp
    assert eval_dir.metadata.version.git_hash == valid_git_hash
    assert eval_dir.metadata_path == pathlib.Path(
        "/path/to/nonexistent/dir/2023-10-26T14:30:00/metadata.json"
    )


def test_eval_results_directory_load_from_path_missing_metadata(tmp_path: pathlib.Path) -> None:
    """`load_from_path` should reconstruct metadata when metadata.json is missing."""
    valid_timestamp = "2023-10-26T14:30:00"

    # Directory name is a valid ISO timestamp
    versioned_dir = tmp_path / valid_timestamp
    versioned_dir.mkdir()

    # Create a minimal summary_metrics.csv so CSV loading succeeds
    summary_csv_path = versioned_dir / ec.SUMMARY_METRICS
    summary_csv_path.write_text("col\n1\n2\n", encoding="utf-8")

    # metadata.json does NOT exist
    metadata_path = versioned_dir / "metadata.json"
    assert not metadata_path.exists()

    # load from path
    eval_dir = lib.BenchmarkDirectory.load_from_path(versioned_dir)

    # Paths are correct
    assert eval_dir.dir_path == versioned_dir
    assert eval_dir.metadata_path == metadata_path
    assert eval_dir.benchmark_results_summary is not None
    assert eval_dir.benchmark_results_summary.summary_csv_path == summary_csv_path

    # Metadata is reconstructed from directory name + git hash
    # Timestamp should match the directory name (ISO-only)
    assert eval_dir.metadata.version.time_stamp == valid_timestamp

    actual_hash = eval_dir.metadata.version.git_hash
    assert actual_hash  # non-empty
    assert validators.is_short_git_hash(actual_hash) is True
