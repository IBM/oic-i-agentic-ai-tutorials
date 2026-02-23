import argparse
import os
from pathlib import Path
import shutil
from typing import Optional

from import_utils.catalog.types import BundleFormatVersion
from import_utils.tool_importer.multifile_tools import build_client_specific_deliverables
from import_utils.utils.logger import get_logger
from import_utils.utils.tools_data_mapper import ToolData, ToolsDataMap

LOGGER = get_logger(__name__)
MAX_FILESIZE_KB = 1024 * 2
# 1 MB * 2, Should aim for less than that. multiply accordingly to readjust.


class ToolZipBuilder:
    """Build Tool Zip Deliverables for Catalog Integration."""

    def __init__(
        self,
        *,
        requirements_path: Path,
        bundle_version: BundleFormatVersion,
        export_dir: Optional[Path] = None,
        keep_temp: bool = False,
    ):
        """
        Args:
            requirements_path: Path to the requirements.txt file
            bundle_version: Bundle version
            export_dir: export_dir path for zip deliverables
            keep_temp: whether to keep temp zip files for debugging purposes
        """
        self.keep_temp = keep_temp

        self.requirements_path = requirements_path
        assert (
            self.requirements_path.exists()
        ), f"Requirements file does not exist: {requirements_path}"

        self.bundle_version = bundle_version

        # Assemble Data
        self.tool_data_mapper = ToolsDataMap()

        if export_dir is not None:
            self.export_dir = export_dir
        else:
            local_import_utils_dir = Path("import_utils").resolve()
            _export_dir = local_import_utils_dir / "tmp_export_tools" / "tool_zip_builder"
            if not _export_dir.exists():
                _export_dir.mkdir(parents=True)
            self.export_dir = _export_dir

        assert (
            self.export_dir.exists() and self.export_dir.is_dir()
        ), f"Not a valid Directory Path: {self.export_dir}"

        # Clean up old if it exists, shouldn't if successful and cleaned up at the end.
        if self.export_dir.exists():
            shutil.rmtree(str(self.export_dir))
        os.makedirs(str(self.export_dir))

    @staticmethod
    def _check_filesize(file_path: Path) -> bool:
        """
        Check if file size meets our criteria.

        Args:
            file_path: file path to check

        Returns:
            True if file size meets our criteria
        """

        file_info = os.stat(str(file_path))
        file_size_bytes = file_info.st_size
        file_size_kb = file_size_bytes / 1024

        return file_size_kb < MAX_FILESIZE_KB

    def _build_zip_archive(self, tool_name: str, target_dir: Path) -> Path:
        """
        Build a zip from the directory containing the deliverable files.

        Args:
            tool_name: name of tool
            target_dir: directory to zip up

        Returns:
            path to zipped archive
        """

        # Path without .zip suffix, will be added in shutil make_archive
        export_zip_path = self.export_dir / f"{tool_name}"
        shutil.make_archive(str(export_zip_path), "zip", str(target_dir))
        return export_zip_path.with_suffix(".zip")

    def _build_temp_workspace(
        self,
        tool_name: str,
        tool_data: ToolData,
    ) -> Path:
        """
        Build a temporary workspace with dependency mapping for a single tool.

        Args:
            tool_name: name of the tool
            tool_data: tool data

        Returns:
            path to temporary workspace containing files for catalog deliverable.
        """
        _, tmp_tool_workspace_dir = build_client_specific_deliverables(
            targeted_tools_data_map={tool_name: tool_data},
            tmp_dir_name=str(tool_name),
        )

        shutil.copy(self.requirements_path, tmp_tool_workspace_dir / "requirements.txt")

        bundle_path = tmp_tool_workspace_dir / "bundle-format"
        fw = open(bundle_path, "w")
        fw.write(self.bundle_version)
        fw.close()

        return tmp_tool_workspace_dir

    def build_tool_zip_deliverable(self, tool_name: str, log_print: bool = True) -> None:
        """
        Build a zip for a single tool by name.

        Args:
            tool_name: name of the tool
            log_print: whether to print a log for each zip deliverable built
        """
        if log_print:
            LOGGER.info(f"Constructing tool zip deliverable for tool: {tool_name}")

        if tool_data := self.tool_data_mapper.get_tool_by_name(tool_name):

            tmp_tool_rel_workspace = self._build_temp_workspace(
                tool_name=tool_name,
                tool_data=tool_data,
            )
        else:
            raise KeyError(f"[ERROR]: Invalid Tool {tool_name} not found.")

        export_zip_path = self._build_zip_archive(tool_name, tmp_tool_rel_workspace)

        if not self._check_filesize(export_zip_path):
            LOGGER.warning(f"{tool_name} zip deliverable exceeds {MAX_FILESIZE_KB} KB")

        if not self.keep_temp:
            shutil.rmtree(str(tmp_tool_rel_workspace))

        if log_print:
            LOGGER.info(f"Tool '{tool_name}' zip deliverable constructed: {str(export_zip_path)}")

    def build_all_tools_zip_deliverables(self) -> None:
        """Build zip deliverables for all tools in repo."""

        for tool_name in self.tool_data_mapper.get_tool_name_to_tool_data_map():
            self.build_tool_zip_deliverable(tool_name=tool_name)


if __name__ == "__main__":

    BUNDLE_VERSION = BundleFormatVersion.V2_0_0
    REQUIREMENTS_PATH = "lite-requirements.txt"

    parser = argparse.ArgumentParser(
        prog="Catalog Tools Builder", description="Build v1.3.0 tools deliverables for the catalog."
    )
    parser.add_argument(
        "-r",
        "--requirements",
        type=str,
        default=REQUIREMENTS_PATH,
        help=f"Path to requirements file. Default: {REQUIREMENTS_PATH} in repo.",
    )
    parser.add_argument(
        "-b",
        "--bundle_version",
        type=BundleFormatVersion,
        default=BUNDLE_VERSION,
        help=f"Bundle version to write into `bundle-format` file. Default: {BUNDLE_VERSION}",
    )
    parser.add_argument(
        "-e",
        "--export_dir",
        type=str,
        default=None,
        help=f'Directory to place zipped archive. Default: "import_utils/tmp_export_tools/tool_zip_builder"',
    )
    parser.add_argument(
        "--keep_temp",
        action="store_true",
        help="Keep temporary workspace after zip building, for debugging purposes.",
    )
    parser.add_argument(
        "--tool",
        type=str,
        help="Build single tool by name.",
    )
    args = parser.parse_args()

    tool_zip_builder = ToolZipBuilder(
        requirements_path=args.requirements,
        bundle_version=args.bundle_version,
        export_dir=args.export_dir,
        keep_temp=args.keep_temp,
    )

    if args.tool:
        tool_zip_builder.build_tool_zip_deliverable(tool_name=args.tool)
    else:
        tool_zip_builder.build_all_tools_zip_deliverables()
