import datetime
import os
import pathlib
import subprocess
import sys
from typing import Any, Optional

from agent_validation.benchmarks.versioning.eval_constants import SUMMARY_METRICS
import pandas as pd
import pydantic
from utils import validators


class BenchmarkVersion(pydantic.BaseModel):
    """Standard version class for classes that use eval result versioning."""

    time_stamp: str
    git_hash: str

    @pydantic.field_validator("time_stamp", mode="after")
    @classmethod
    def _is_iso_format(cls, value: str) -> str:
        """Validate timestamp field is in ISO format %Y-%m-%dT%H:%M:%S."""
        if validators.is_iso_format(value) is False:
            raise ValueError(f"{value} is not a valid timestamp.")
        return value

    @pydantic.field_validator("git_hash", mode="after")
    @classmethod
    def _is_short_git_hash(cls, value: str) -> str:
        """Validate git_hash with `is_short_git_hash` validator."""
        if validators.is_short_git_hash(value) is False:
            raise ValueError(f"{value} is not a valid short git hash.")
        return value


class BenchmarkMetadata(pydantic.BaseModel):
    """
    Eval results metadata standard class.

    Make all fields additional to `version` optional for backwards compatibility.
    """

    version: BenchmarkVersion

    def to_json(self) -> dict[str, Any]:
        """Serialize to JSON."""
        return self.model_dump(mode="json")

    @classmethod
    def from_json_string(cls, json_string: str) -> "BenchmarkMetadata":
        """Deserialize an `BenchmarkMetadata` object from a JSON string."""
        return cls.model_validate_json(json_string)


class BenchmarkResultsSummary(pydantic.BaseModel):
    """Eval Benchmark result summary."""

    model_config = pydantic.ConfigDict(validate_assignment=True, arbitrary_types_allowed=True)

    summary_csv_path: pathlib.Path
    dataframe: pd.DataFrame


class BenchmarkDirectory(pydantic.BaseModel):
    """Standard eval benchmark directory definition."""

    model_config = pydantic.ConfigDict(validate_assignment=True)

    dir_path: pathlib.Path
    benchmark_results_summary: Optional[BenchmarkResultsSummary] = None

    # The metadata of the benchmarks
    metadata: BenchmarkMetadata
    metadata_path: pathlib.Path

    results: None = None  # TODO: Model the eval output result of the dir

    @pydantic.field_validator("dir_path", mode="after")
    @classmethod
    def _is_versioned_dir(cls, value: pathlib.Path) -> pathlib.Path:
        """Validator for versioned dir."""
        if not validators.is_iso_format(value.parts[-1]):
            raise ValueError(f"{value} does not contain a valid timestamp.")
        return value

    @pydantic.field_validator("metadata_path", mode="after")
    @classmethod
    def _is_versioned_metadata_file(cls, value: pathlib.Path) -> pathlib.Path:
        """Validator for versioned metadata files."""
        if not validators.is_iso_format(value.parts[-2]):
            raise ValueError(f"{value} does not contain a valid timestamp.")
        if value.parts[-1] != "metadata.json":
            raise ValueError(f"{value} is not a metadata.json file.")
        return value

    @classmethod
    def build(
        cls,
        dir_path: str,
        *,
        version: BenchmarkVersion | None = None,
    ) -> "BenchmarkDirectory":
        """Build an BenchmarkDirectory instance from a directory."""
        _version = generate_version() if version is None else version
        versioned_path = pathlib.Path(os.path.join(dir_path, _version.time_stamp))
        metadata_path = pathlib.Path(os.path.join(versioned_path, "metadata.json"))

        return cls(
            dir_path=versioned_path,
            metadata=BenchmarkMetadata(version=_version),
            metadata_path=metadata_path,
        )

    @classmethod
    def load_from_path(cls, versioned_dir_path: pathlib.Path) -> "BenchmarkDirectory":
        """Finds and loads the CSV from an *existing* benchmark directory."""

        try:
            csv_files_found = list(versioned_dir_path.rglob(SUMMARY_METRICS))
        except FileNotFoundError:
            msg = f"Benchmark directory not found at: {versioned_dir_path}"
            raise FileNotFoundError(msg)

        if not csv_files_found:
            msg = f"No summary CSV matching '{SUMMARY_METRICS}' under: {versioned_dir_path}"
            print(msg, file=sys.stderr)
            raise FileNotFoundError(msg)

        summary_csv_path = csv_files_found[0]

        try:
            loaded_df = pd.read_csv(summary_csv_path)
        except FileNotFoundError:
            msg = f"Summary CSV not found at: {summary_csv_path}"

            raise FileNotFoundError(msg)

        summary = BenchmarkResultsSummary(summary_csv_path=summary_csv_path, dataframe=loaded_df)

        metadata_path = pathlib.Path(os.path.join(versioned_dir_path, "metadata.json"))
        loaded_metadata: BenchmarkMetadata | None = None

        if metadata_path.exists():
            # Try reading metadata.json
            try:
                metadata_content = metadata_path.read_text(encoding="utf-8")
            except OSError as e:
                # Can't read the file at all -> fall back to reconstruction
                print(
                    f"Failed to read metadata.json at {metadata_path}: {e}",
                    file=sys.stderr,
                )
            else:
                # Parsing metadata.json
                try:
                    loaded_metadata = BenchmarkMetadata.from_json_string(metadata_content)
                except ValueError as e:
                    print(
                        f"Failed to parse metadata.json at {metadata_path}: {e}",
                        file=sys.stderr,
                    )

        if loaded_metadata is None:
            # Reconstruct from directory name + git hash (ISO-only)
            loaded_metadata = _reconstruct_metadata_from_dir(versioned_dir_path)

        return cls(
            dir_path=versioned_dir_path,
            benchmark_results_summary=summary,
            metadata=loaded_metadata,
            metadata_path=metadata_path,
            results=None,
        )

    # TODO: Write classmethod to construct cls from an existing eval results dir


def get_git_revision_short_hash() -> str:
    """Get the short git hash of the current commit."""
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,  # hide 'not a git repo' noise
            )
            .decode("utf-8")
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        # Valid-looking 7-char short hash placeholder
        return "0000000"


def get_timestamp() -> str:
    """Get the current time as a timestamp."""
    now = datetime.datetime.now(datetime.timezone.utc).now()
    now_without_microseconds = now.replace(microsecond=0)
    return now_without_microseconds.isoformat()


def generate_version() -> "BenchmarkVersion":
    """Generate an eval results version."""
    return BenchmarkVersion(
        time_stamp=get_timestamp(),
        git_hash=get_git_revision_short_hash(),
    )


def _reconstruct_metadata_from_dir(versioned_dir_path: pathlib.Path) -> BenchmarkMetadata:
    """
    Reconstruct `BenchmarkMetadata` from the directory name and current git hash.

    This requires the directory name (last path component) to already be a valid ISO timestamp.
    """
    ts_norm = versioned_dir_path.name

    # ISO format only
    if not validators.is_iso_format(ts_norm):
        raise ValueError(f"{versioned_dir_path} does not contain a valid timestamp dir.")

    try:
        gh = get_git_revision_short_hash()
    except FileNotFoundError as e:
        msg = "Could not obtain short git hash to reconstruct metadata."
        raise RuntimeError(msg) from e

    # BenchmarkVersion / BenchmarkMetadata validation errors propagate
    return BenchmarkMetadata(version=BenchmarkVersion(time_stamp=ts_norm, git_hash=gh))
