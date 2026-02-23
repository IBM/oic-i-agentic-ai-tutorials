import argparse
from pathlib import Path
import shutil
import tempfile
from typing import Any, Dict, List

from import_utils.catalog.metadata.catalog_metadata import CatalogMetadata
from import_utils.catalog.metadata.validation.metadata_validator import MetadataValidator
from import_utils.catalog.release_config_data import CollaboratorPath, ReleaseConfigData
from import_utils.catalog.tool_zip_builder import ToolZipBuilder
from import_utils.catalog.types import BundleFormatVersion, PublisherName
from import_utils.utils.logger import get_logger
import more_itertools
from pydantic_extra_types.semantic_version import SemanticVersion  # pants: no-infer-dep
import typer
from utils.directory.path_validators import is_valid_dir_path, is_valid_excel_filepath
from utils.version.version_validators import is_valid_version

LITE_REQUIREMENTS_PATH = Path("lite-requirements.txt")
MAIN_REQUIREMENTS_PATH = Path("3rdparty/python/requirements.txt")

COLLABORATOR_DIR = Path("collaborator_agents")

ADDITIONAL_TOOL_REQS = ["ibm-watsonx-orchestrate"]

DEFAULT_PUBLISHER_NAME = PublisherName.IBM

LOGGER = get_logger(__name__)


def write_all_data(release_config: ReleaseConfigData, export_dir: Path) -> None:
    """
    Writes offering/agent/tool deliverables to their prescribed filepaths.

    Args:
        release_config: The ReleaseConfigData to write to filepath.
        export_dir: The base directory where all deliverables should be exported.
    """
    model_dump_json_kwargs: Dict[str, Any] = {
        "indent": 4,
        "exclude_none": True,
    }

    for offering_config in release_config.offerings_config_data.data:
        LOGGER.info(
            f"Constructing deliverables for offering: {offering_config.offering_config_spec.name}..."
        )

        # Create offering config.json
        write_to_filepath(
            payload=offering_config.offering_config_spec.model_dump_json(**model_dump_json_kwargs),
            base_dir=export_dir,
            rel_filepath=offering_config.relative_export_filepath,
        )

    for agent_config in release_config.agents_config_data:
        LOGGER.info(
            f"Constructing deliverables for agent: {agent_config.agent_config_spec.name}..."
        )

        # Create agents config.json
        write_to_filepath(
            payload=agent_config.agent_config_spec.model_dump_json(**model_dump_json_kwargs),
            base_dir=export_dir,
            rel_filepath=agent_config.relative_export_filepath,
        )

    for tool_config in release_config.tools_config_data:
        LOGGER.info(f"Constructing deliverables for tool: {tool_config.tool_config_spec.name}...")

        # Create tool config.json
        write_to_filepath(
            payload=tool_config.tool_config_spec.model_dump_json(**model_dump_json_kwargs),
            base_dir=export_dir,
            rel_filepath=tool_config.relative_export_filepath,
        )
        # Create tool <tool_name>.zip
        # TODO: pass requirements_path via a flag
        _rel_tool_zip_dir = tool_config.relative_export_filepath.parent / "attachments"
        _additional_reqs = get_versioned_requirements_from_file(
            requirements_file=MAIN_REQUIREMENTS_PATH, requirement_names=ADDITIONAL_TOOL_REQS
        )

        write_tool_zip_to_filepath(
            tool_name=tool_config.tool_name,
            base_dir=export_dir,
            rel_dir_path=_rel_tool_zip_dir,
            requirements_path=LITE_REQUIREMENTS_PATH,
            additional_reqs=_additional_reqs,
        )

    # Write applications config data
    for applications_config in release_config.applications_config_data:
        # Create applications config.json
        write_to_filepath(
            payload=applications_config.applications_config_spec.model_dump_json(
                **model_dump_json_kwargs
            ),
            base_dir=export_dir,
            rel_filepath=applications_config.relative_export_filepath,
        )


def write_to_filepath(*, payload: str, base_dir: Path, rel_filepath: Path) -> None:
    """
    Write a specified payload to a filepath.

    Args:
        payload: the payload to write to filepath
        base_dir: the base dir
        rel_filepath: relative filepath
    """
    path = (base_dir / rel_filepath).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload)
    LOGGER.info(f"Deliverable constructed: {str(rel_filepath)}")


def get_validated_versioned_requirements(
    requirement_data: List[str],
    requirement_names: List[str],
) -> List[str]:
    """
    Extract and validate versioned requirements from requirements file data.

    Args:
        requirements_file: the requirements data from file
        requirement_names: the list of requirements to query from requirements file

    Returns:
        the versioned requirements pulled from the provided requirements file
    """
    result = []
    for req in requirement_names:
        try:
            _versioned_req = [x.strip() for x in requirement_data if x.startswith(req)]
            result.append(more_itertools.one(_versioned_req))
        except ValueError:
            if _versioned_req:
                msg = f"Requirements data contains multiple matches for requirement {req!r}"
            else:
                msg = f"Requirements data contains no matches for requirement {req!r}"
            raise ValueError(msg)
    return result


def get_versioned_requirements_from_file(
    requirements_file: Path,
    requirement_names: List[str],
) -> List[str]:
    """
    Get a versioned requirement from a requirements file, if there is any, otherwise, return None.

    Args:
        requirements_file: the requirements file
        requirement_names: the list of requirements to query from requirements file

    Returns:
        the versioned requirements pulled from the provided requirements file
    """
    with open(requirements_file, "r") as fp:
        return get_validated_versioned_requirements(fp.readlines(), requirement_names)


def write_tool_zip_to_filepath(
    *,
    tool_name: str,
    base_dir: Path,
    rel_dir_path: Path,
    requirements_path: Path,
    additional_reqs: List[str] | None = None,
) -> None:
    """
    Write tool zip deliverable to filepath.

    Args:
        tool_name: the name of the tool for which to create and write zip deliverable
        base_dir: the base dir
        rel_dir_path: relative dir path
        requirements_path: the path to the requirements file to use
        additional_reqs: the additional reqs to include in requirements file
    """
    export_dir_path = (base_dir / rel_dir_path).resolve()
    export_dir_path.mkdir(parents=True, exist_ok=True)

    if additional_reqs:
        # Create a temporary 'requirements.txt' file with the additional requirements.
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            requirements_plus_path = (tmpdir_path / "requirements.txt").resolve()
            base_reqs = requirements_path.read_text().splitlines()
            requirements_plus_path.write_text("\n".join(additional_reqs + base_reqs))

            tool_zip_builder = ToolZipBuilder(
                requirements_path=requirements_plus_path,
                export_dir=export_dir_path,
                bundle_version=BundleFormatVersion.V2_0_0,
            )
            tool_zip_builder.build_tool_zip_deliverable(tool_name=tool_name)

    else:
        tool_zip_builder = ToolZipBuilder(
            requirements_path=requirements_path,
            export_dir=export_dir_path,
            bundle_version=BundleFormatVersion.V2_0_0,
        )
        tool_zip_builder.build_tool_zip_deliverable(tool_name=tool_name)


def main() -> None:
    """Generates and exports offering/agent/tool config files in the format prescribed for 'catalog'
    ingestion."""

    parser = argparse.ArgumentParser(
        description="Generate and export offering/agent/tool config files for catalog."
    )
    parser.add_argument(
        "-e",
        "--export_dir",
        type=is_valid_dir_path,
        required=True,
        help="Target directory to export all config folders and files.",
    )
    parser.add_argument(
        "-z",
        "--save_to_zip",
        action="store_true",
        help="Whether to export all config folders and files in a zip file.",
    )
    parser.add_argument(
        "-v",
        "--version",
        type=is_valid_version,
        required=True,
        help="The version for this release of catalog offerings.",
    )
    parser.add_argument(
        "-m",
        "--metadata_filepath",
        type=is_valid_excel_filepath,
        required=True,
        help="The path to the Excel file containing all catalog metadata.",
    )

    # TODO: flags to add:
    # --verbose: (optional) whether to print all the logs while constructing deliverables or not
    # --requirements_path: (optional) path to the requirements file associated with tools

    args = parser.parse_args()

    export_dir = Path(args.export_dir)
    version = SemanticVersion.parse(args.version)
    metadata_filepath = Path(args.metadata_filepath)

    # TODO: Define these without having to parse dirs, via command line args, etc.
    # Parse the directories to get the collaborator agents.
    source_dir = Path(__file__).parent.parent.parent
    collaborator_dir = source_dir / COLLABORATOR_DIR
    collaborator_dir = collaborator_dir.relative_to(source_dir)
    collaborator_path = CollaboratorPath(collaborator_dir)
    try:
        is_valid_dir_path(collaborator_path.path)
    except ValueError as e:
        LOGGER.error(f"The collaborator_agents path configured is invalid.")
        raise ValueError(e)

    LOGGER.info(f"Loading catalog metadata from {metadata_filepath}")
    catalog_metadata = CatalogMetadata.from_filepath(metadata_filepath)
    metadata_validator = MetadataValidator(metadata=catalog_metadata)

    proceed_with_export = False

    if metadata_validator.missing_metadata:
        LOGGER.warning(f"⚠️  Metadata is missing entries/fields:\n")
        metadata_validator.print_missing_metadata_report()

        if typer.confirm("\nThere are missing metadata entries/fields. Do you want to proceed?"):
            LOGGER.info("Proceeding with catalog artifact generation...")
            proceed_with_export = True
        else:
            LOGGER.info("Aborting catalog artifact generation...")
            proceed_with_export = False
    else:
        LOGGER.info(f"✅  Metadata is not missing any entries/fields!")

    if proceed_with_export:
        release_config = ReleaseConfigData.build(
            collaborator_dir=collaborator_path,
            catalog_metadata=catalog_metadata,
            publisher=DEFAULT_PUBLISHER_NAME,
            version=version,
        )

        LOGGER.info(f"📄 The following offerings are included as part of this release:")
        metadata_validator.print_missing_metadata_report()

        # Write files
        if args.save_to_zip:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)
                zip_path = (export_dir / "catalog_configs").resolve()

                write_all_data(
                    release_config=release_config,
                    export_dir=tmpdir_path,
                )
                shutil.make_archive(str(zip_path), "zip", tmpdir_path)
                LOGGER.info(f"Zip file saved as {zip_path}.zip")
        else:
            write_all_data(
                release_config=release_config,
                export_dir=export_dir,
            )
            LOGGER.info(f"\nAll config files saved at {(export_dir).resolve()}")


if __name__ == "__main__":
    main()
