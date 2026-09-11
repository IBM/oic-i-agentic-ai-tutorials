import os
from pathlib import Path
from typing import Mapping

from ibm_watsonx_orchestrate.agent_builder.agents import Agent
import yaml


def get_agents_in_directory(root_folder: str) -> list[Agent]:
    """
    Recursively loads all agent YAML files in all subdirectories of the given folder.

    Args:
        root_folder: The root directory to search for YAML files.

    Returns:
        List of agents parsed from YAML files.
    """
    agents = []
    for dirpath, _, filenames in os.walk(root_folder):
        for filename in filenames:
            if filename.endswith((".yaml", ".yml")):
                file_path = os.path.join(dirpath, filename)
                agent = Agent.from_spec(file_path)
                agents.append(agent)
    return agents


def find_agent_yamls(collaborator_rel_dir: Path) -> Mapping[str, Path]:
    """
    Catalog all potential agent files.

    Args:
        collaborator_rel_dir: The collaborator relative directory path, which should point to local env.

    Returns:
        Map of agent yaml paths keyed on agent name defined within the file.
    """
    yaml_mapping = {}
    for root, _, files in collaborator_rel_dir.walk():
        for file in files:
            if not (file.endswith(".yaml") or file.endswith(".yml")):
                continue
            yaml_path = root / file
            yaml_data = yaml.safe_load(yaml_path.read_text())
            yaml_mapping[yaml_data["name"]] = yaml_path

    return yaml_mapping
