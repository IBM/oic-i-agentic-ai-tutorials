from import_utils.utils.constants import SUPPORTED_LLMS_FOR_AGENTS
from import_utils.utils.get_agent_yaml import get_agents_in_directory


def test_all_agents_use_a_supported_model() -> None:
    """Test that all agents are using a supported model."""
    agent_dir = "collaborator_agents/"
    all_agents = get_agents_in_directory(agent_dir)
    assert len(all_agents) > 0, f"ensure that agent yaml files are in the agent dir: {agent_dir} "
    for agent in all_agents:
        assert agent.llm in SUPPORTED_LLMS_FOR_AGENTS, f"{agent.llm} is not supported"
