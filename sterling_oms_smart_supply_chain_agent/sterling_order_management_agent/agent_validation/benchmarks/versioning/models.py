from pathlib import Path
from typing import Optional

from agent_validation.benchmarks.versioning import eval_constants as ec
from pydantic import BaseModel, Field, field_validator
from pydantic.dataclasses import dataclass
from utils.directory.path_validators import is_valid_dir_path


class DomainRequest(BaseModel):
    """What domain we are scanning and where to find it."""

    test_dir: Path = Field(default_factory=lambda: ec.ADK_TEST_CASES_DIR_PATH)
    domain_name: str = Field(..., min_length=1)
    dataset_glob: str = Field(default_factory=lambda: ec.DEFAULT_DATASET_GLOB)
    case_insensitive: bool = Field(True)

    @field_validator("test_dir", mode="before")
    @classmethod
    def _validate_test_dir(cls, v: Path) -> Path | str:
        return is_valid_dir_path(v)


@dataclass(frozen=True)
class DomainScanResult:
    """Result of scanning the FS for a given domain."""

    domain_name: str
    dataset_name: str
    agent: Optional[str]
    file_path: str


@dataclass(frozen=True)
class CsvFilterResult:
    """Structured outcome of the CSV filtering step."""

    domain: str
    kept_rows: int
    total_rows: int
    output_file: Optional[Path] = None
