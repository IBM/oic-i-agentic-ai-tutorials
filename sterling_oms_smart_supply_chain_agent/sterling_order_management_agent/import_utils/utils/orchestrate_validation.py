import sys

import ibm_watsonx_orchestrate
from packaging.version import Version


def version_check(cli_version: str) -> None:
    """
    Check CLI version and verify against the pants version.

    Args:
        cli_version: CLI version from bash script.
    """
    imported_ver = Version(ibm_watsonx_orchestrate.__version__)
    cli_ver = Version(cli_version)
    if imported_ver > cli_ver:
        raise ValueError(
            f"Orchestrate version {cli_version} does not meet min requirement: {imported_ver}. Please Update."
        )


if __name__ == "__main__":
    version_check(sys.argv[1])
