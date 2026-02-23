from pathlib import Path
from typing import List, Optional

from ibm_watsonx_orchestrate.cli.commands.agents.agents_command import agent_import
from import_utils.tool_importer.agent_yamls_data import AgentYamlsData

DOMAIN_DIRS = {
    "hr": [
        "hr/employee_support/sap_successfactors",
        "hr/employee_support/workday",
        "hr/employee_support/oracle_hcm",
    ],
    "sales": ["sales"],
    "procurement": ["procurement/coupa"],
    "productivity": [
        "productivity/servicenow",
        "productivity/box",
        "productivity/google_drive",
        "productivity/jira",
        "productivity/outlook",
        "productivity/teams",
        "productivity/slack",
        "productivity/sharepoint",
    ],
}


def get_domain_managers(domain: str, collaborator_yaml_dir: Path) -> List[Path]:
    """
    Gets list of manager files for a specific domain.

    Args:
        domain: domain name to obtain all managers files for
        collaborator_yaml_dir: Root directory for collaborator agent YAML files.

    Returns:
        List of all managers files for a given domain
    """

    domain_managers = []

    for dir_rel_path in DOMAIN_DIRS.get(domain, []):
        dir_path = collaborator_yaml_dir / dir_rel_path
        if not dir_path.is_dir():
            continue
        # Find all .yaml manager files in the directory
        domain_managers.extend(
            sorted(
                f
                for f in dir_path.iterdir()
                if f.is_file()
                and f.suffix == ".yaml"
                and str(Path(f).with_suffix("")).lower().endswith("manager")
            )
        )

    return domain_managers


def get_topological_order_for_domain(domain: str, collaborator_yaml_dir: Path) -> List[str]:
    """
    Gets topological order of agent files for a given domain.

    Args:
        domain: domain name to obtain all agents for
        collaborator_yaml_dir: Root directory for collaborator agent YAML files.

    Returns:
        List of all agent files in a topological order
    """
    all_managers = get_domain_managers(domain=domain, collaborator_yaml_dir=collaborator_yaml_dir)

    load_order_filepaths = []
    for manager_file in all_managers:
        filepaths = AgentYamlsData(manager_filepath=manager_file).get_topological_order_filepaths()
        load_order_filepaths.extend(filepaths)

    return load_order_filepaths


def get_agents_files(
    collaborator_yaml_dir: Path, domain: Optional[str] = None, manager: Optional[Path] = None
) -> List[str]:
    """
    Retrieves a list of agent YAML file paths in topological import order.

    Either a specific manager file can be used directly, or all applicable
    manager files within the given domain are used. A manager file is identified as:
      - The only `.yaml` file in a directory, or
      - A `.yaml` file whose name contains 'manager'.

    Args:
        collaborator_yaml_dir: Root directory for collaborator agent YAML files.
        domain: Domain used to locate subdirectories with YAML files.
        manager: Specific manager YAML file path to use.

    Returns:
        List[Path]: YAML file paths to import in the correct order.
    """

    if manager:
        return AgentYamlsData(manager_filepath=manager).get_topological_order_filepaths()
    elif domain:
        load_order_filepaths = get_topological_order_for_domain(
            domain=domain, collaborator_yaml_dir=collaborator_yaml_dir
        )

        if not load_order_filepaths:
            raise ValueError(f"No manager files found in domain '{domain}'.")

        return load_order_filepaths
    else:
        raise ValueError(f"Either manager or domain has to be provided")


def import_agents(
    collaborator_yaml_dir: Path, domain: Optional[str], manager: Optional[Path]
) -> None:
    """
    Imports agent definitions by loading them from YAML files based on the specified domain or
    manager.

    This function retrieves the correct file load order and calls `agent_import()` for each file.

    Args:
        collaborator_yaml_dir: The root directory where collaborator agent YAML files are stored.
        domain: The domain used to locate relevant agent directories (if `manager` is not provided).
        manager: Path to a manager YAML file (if used to determine load order).
    """
    load_order = get_agents_files(
        domain=domain, manager=manager, collaborator_yaml_dir=collaborator_yaml_dir
    )
    for file in load_order:
        agent_import(file=file)
