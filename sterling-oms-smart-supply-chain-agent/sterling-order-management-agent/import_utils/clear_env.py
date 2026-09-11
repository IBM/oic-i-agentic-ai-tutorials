import json
from typing import Annotated

from ibm_watsonx_orchestrate.cli.commands.agents.agents_command import remove_agent
from ibm_watsonx_orchestrate.cli.commands.agents.agents_controller import AgentsController
from ibm_watsonx_orchestrate.cli.commands.connections.connections_controller import (
    remove_connection,
)
from ibm_watsonx_orchestrate.cli.commands.partners.offering.types import AgentKind
from ibm_watsonx_orchestrate.cli.commands.tools.tools_controller import ToolsController
from ibm_watsonx_orchestrate.client.connections import get_connections_client
from import_utils.utils.logger import get_logger
import typer

from agent_ready_tools.utils.env import in_adk_env

app = typer.Typer(no_args_is_help=True)
_logger = get_logger(__name__)


@app.command(name="local", help="Clear local environment of all tools, agents, and connections.")
def clear_local_env(
    ignore_connections: Annotated[
        bool, typer.Option("--ignore_connections", help="Don't clear connections.")
    ] = False,
) -> None:
    """Clear local environment of all tools, agents, and connections without having to reset the
    server."""

    assert in_adk_env(), "Not in local env."

    # Remove all Tools
    tools_controller = ToolsController()

    for tool_name in tools_controller.get_all_tools():
        _logger.info(f"Removing tool: {tool_name}")
        tools_controller.remove_tool(tool_name)

    # Remove all Agents
    agent_control = AgentsController()
    native_agents, _ = agent_control._fetch_and_parse_agents(  # pylint: disable=protected-access
        AgentKind.NATIVE
    )

    agents_list = []
    for agent in native_agents:
        agents_list.append(json.loads(agent.dumps_spec()))

    for agent_dict in agents_list:
        agent_name = agent_dict["name"]
        # Also available if needed:
        #   agent_dict["id"]
        #   agent_dict["display_name"]

        _logger.info(f"Removing agent: {agent_name}")
        remove_agent(agent_name, AgentKind.NATIVE)

    # Remove all Connections
    if not ignore_connections:
        conns_client = get_connections_client()

        conns_list = conns_client.list()
        unique_app_ids = set()
        for conn in conns_list:
            app_id = conn.app_id
            unique_app_ids.add(app_id)

        for app_uid in unique_app_ids:
            _logger.info(f"Removing connection app-id: {app_uid}")
            remove_connection(app_uid)


if __name__ == "__main__":
    app()
