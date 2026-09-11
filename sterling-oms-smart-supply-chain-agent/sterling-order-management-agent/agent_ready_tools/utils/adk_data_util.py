import os
from typing import List

from ibm_watsonx_orchestrate.cli.commands.agents.agents_controller import Agent, AgentsController


def load_agents(path: str, api_id: str) -> List[Agent]:
    """Loads agents from the collaborator_agents directory."""

    directory = f"{os.curdir}/{path}/"
    assert os.path.isdir(directory), f"Directory {directory} does not exist."

    agents = []
    for file in os.listdir(directory):
        if not file.endswith(".yaml"):
            continue

        agent_path = f"{directory}/{file}"
        agent = AgentsController.import_agent(agent_path, app_id=api_id)

        assert len(agent) == 1, f"Agent {file} wasn't imported correctly."

        agents.append(agent[0])
    return agents
