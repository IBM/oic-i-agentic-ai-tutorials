from dataclasses import asdict
from typing import Annotated, List, Optional

from import_utils.catalog.repo_artifact_inventory.repo_artifact_inventory import (
    build_repo_artifact_inventory,
)
from rich.console import Console
from rich.pretty import pretty_repr
import typer

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command(name="generate_artifact_inventory")
def generate_artifact_inventory_cmd(
    only_managers: Annotated[
        Optional[List[str]],
        typer.Option(
            "--only_managers",
            "-m",
            help="List of managers to generate artifacts for. If unspecified, all artifacts will be inventoried.",
        ),
    ] = None,
) -> None:
    """Validate the raw data in the metadata file."""

    try:
        artifact_inventory = build_repo_artifact_inventory(only_managers=only_managers)
    except AssertionError as e:
        raise AssertionError(f"Error while generating repo artifact inventory: {e}")
    console.print(f"REPO ARTIFACT INVENTORY: \n{pretty_repr(asdict(artifact_inventory))}")


if __name__ == "__main__":
    app()
