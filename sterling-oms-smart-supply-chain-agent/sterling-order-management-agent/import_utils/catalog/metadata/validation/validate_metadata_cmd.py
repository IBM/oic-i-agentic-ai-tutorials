from pathlib import Path
from typing import Annotated

from import_utils.catalog.metadata.catalog_metadata import CatalogMetadata
from import_utils.catalog.metadata.raw_metadata.raw_metadata import RawCatalogMetadata
from import_utils.catalog.metadata.raw_metadata.validation import validate_raw_metadata
from import_utils.catalog.metadata.validation.metadata_validator import MetadataValidator
from import_utils.utils.logger import get_logger
from rich.console import Console
import typer

LOGGER = get_logger(__name__)

app = typer.Typer(no_args_is_help=True)
console = Console()

# Passing in a string instead of __name__ since this will usually be "__main__"
LOGGER = get_logger("validate_metadata")


@app.command(name="validate_raw_metadata")
def validate_raw_metadata_cmd(
    metadata_filepath: Annotated[
        Path,
        typer.Option(
            "--metadata_filepath",
            "-m",
            help="Filepath to metadata file",
        ),
    ],
) -> None:
    """Validate the raw data in the metadata file."""

    assert (
        metadata_filepath.exists() and metadata_filepath.is_file()
    ), f"'{metadata_filepath}' is not a valid filepath"
    assert metadata_filepath.suffix in [
        ".xls",
        ".xlsx",
        ".xlsm",
        ".xlsb",
    ], f"File: {metadata_filepath} is not a valid Excel file."

    try:
        raw_metadata = RawCatalogMetadata.from_filepath(filepath=metadata_filepath)
        validate_raw_metadata(raw_metadata=raw_metadata)
    except AssertionError as e:
        raise AssertionError(f"Error found in metadata file: {e}")
    LOGGER.info(f"No errors found in metadata file: {metadata_filepath}.")


@app.command(name="validate_catalog_metadata")
def validate_catalog_metadata_cmd(
    metadata_filepath: Annotated[
        Path,
        typer.Option(
            "--metadata_filepath",
            "-m",
            help="Filepath to metadata file",
        ),
    ],
) -> None:
    """
    Validates the existing repo artifacts against entries/fields in a metadata file and prints a
    couple of metadata reports:

    - Report of missing entries/fields in the provided metadata file (if any)
    - Report of all offerings/manager agents defined in metadata
    """

    metadata = CatalogMetadata.from_filepath(filepath=metadata_filepath)
    metadata_validator = MetadataValidator(metadata=metadata)

    if metadata_validator.has_missing_metadata:
        console.print(f"⚠️  Metadata is missing entries/fields:", style="yellow")
        metadata_validator.print_missing_metadata_report(console=console)

        console.print(
            f"\n⚠️  The following OFFERINGS REPORT may be incomplete if there is missing metadata:",
            style="yellow",
        )
        metadata_validator.print_offerings_report(console=console)
    else:
        console.print(f"✅  Metadata is not missing any entries/fields!", style="green")
        metadata_validator.print_offerings_report(console=console)


if __name__ == "__main__":
    app()
