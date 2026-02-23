from pathlib import Path
from typing import List, Optional

from ibm_watsonx_orchestrate.cli.commands.tools.tools_controller import ToolsController
from import_utils.agent_importer.agent_import import DOMAIN_DIRS, get_domain_managers, import_agents
from import_utils.connections.import_connections import ConnectionManager
from import_utils.tool_importer.agent_yamls_data import AgentYamlsData
from import_utils.tool_importer.eval_patch_tools import eval_patch_tools_import
from import_utils.tool_importer.mcp_tools import (
    extract_toolkits,
    get_toolkits_mapping,
    mcp_tools_import,
)
from import_utils.tool_importer.multifile_tools import multi_file_tool_import
from import_utils.tool_importer.tag_to_manager_mapper import TagToManagerMapper
from import_utils.utils.logger import get_logger
from import_utils.utils.tools_data_mapper import ToolsDataMap
import typer
from typing_extensions import Annotated

# TODO: Create subcommands for different arguments: [manager, domain, update_tool]
app = typer.Typer(no_args_is_help=True)

# Passing in a string instead of __name__ since this will usually be "__main__"
LOGGER = get_logger("import_command")

# Note: Relative paths will resolve to local dev machine.
COLLABORATOR_REL_DIR = Path("collaborator_agents")
CREDENTIALS_REL_PATH = Path("agent_ready_tools/utils/credentials.json")
LITE_REQUIREMENTS_REL_PATH = Path("lite-requirements.txt")


@app.command(name="mcp")
def mcp_import_command(
    toolkit: Annotated[
        Path,
        typer.Option(
            "--toolkit",
            help="Path to mcp toolkit manager config file.",
        ),
    ],
) -> None:
    """Import MCP toolkit defined by MCP agent yaml."""
    toolkits_map = get_toolkits_mapping(Path("mcp"))
    toolkits_list = extract_toolkits(toolkit)

    for toolkit_name in toolkits_list:
        package_root = toolkits_map[toolkit_name]

        mcp_tools_import(package_root=package_root, mcp_yaml=toolkit)

    import_agents(
        collaborator_yaml_dir=Path("mcp/collaborator_agents"), domain=None, manager=toolkit
    )


@app.command(name="python")
def python_import_command(
    collaborator_yaml_dir: Annotated[
        Path,
        typer.Option(
            "--collaborator_yaml_dir",
            help="Path to collaborator agents main directory. Default: './collaborator_agents/'",
        ),
    ] = COLLABORATOR_REL_DIR,
    json_creds_file: Annotated[
        Path,
        typer.Option(
            "--json_creds_file",
            help="Path to the credentials.json file. Default: './agent_ready_tools/utils/credentials.json'",
        ),
    ] = CREDENTIALS_REL_PATH,
    requirements_file: Annotated[
        Optional[Path],
        typer.Option(
            "--requirements_file",
            "-r",
            help="Path to the requirements_file. Default: './lite-requirements.txt'",
        ),
    ] = LITE_REQUIREMENTS_REL_PATH,
    manager: Annotated[
        Optional[Path],
        typer.Option(
            "--manager",
            "-m",
            help="Path to the manager agent yaml to build dependencies from.",
        ),
    ] = None,
    domain: Annotated[
        Optional[str],
        typer.Option(
            "--domain",
            "-d",
            help="Specify a domain for which to load tools/agents. The default is 'hr'",
        ),
    ] = None,
    force_import_connections: Annotated[
        bool,
        typer.Option(
            "--force_import_connections",
            help="Force import connections for orchestrate. If a required connection exists, it will be deleted and recreated.",
        ),
    ] = False,
    update_tool: Annotated[
        Optional[str],
        typer.Option("--update_tool", help="Update a single tool by tool_name."),
    ] = None,
    resume_import: Annotated[
        bool,
        typer.Option(
            "--resume_import",
            help="If there is a failure in importing, resume from where we left off.",
        ),
    ] = False,
    load_agents_only: Annotated[
        bool, typer.Option("--load_agents_only", help="Load only agent definitions, not tools")
    ] = False,
    supported_manager_tags: Annotated[
        bool,
        typer.Option("--supported_manager_tags", help="Print all supported manager tags."),
    ] = False,
    mock_eval: Annotated[
        Optional[str],
        typer.Option(
            "--mock_eval",
            help="Path to mock yaml in `mock_data/adk_vcr`. Trigger injection of mocked clients for eval usage. For ADK Eval usage.",
        ),
    ] = None,
) -> None:
    """Build deliverable and import all Python tools per manager file."""

    if supported_manager_tags:
        TagToManagerMapper().print_supported_manager_tags()
        raise typer.Exit()

    assert (
        requirements_file and requirements_file.exists()
    ), f"Requirements file not found: {requirements_file}"
    assert json_creds_file.exists(), f"Credentials file not found: {json_creds_file}"
    assert (
        collaborator_yaml_dir.exists() and collaborator_yaml_dir.is_dir()
    ), f"Collaborator yaml directory not found: {collaborator_yaml_dir}"

    targeted_tools: List[str] = []
    manager_ids: List[str] = []

    if domain and domain not in DOMAIN_DIRS:
        valid_domains = ", ".join(list(DOMAIN_DIRS.keys()))
        raise ValueError(f"Invalid domain. Valid domains: '{valid_domains}'")

    validate_args = sum(x is not None for x in [domain, update_tool, manager])
    if validate_args == 0:
        raise ValueError("No required arguments found. [--manager, --update_tool, --domain]")
    if validate_args > 1:
        raise ValueError("Only one argument can be used. [--manager, --update_tool, --domain]")

    if load_agents_only and any([domain, manager]):
        LOGGER.info("Skipping tool imports. Loading only collaborator agents...")
        import_agents(domain=domain, manager=manager, collaborator_yaml_dir=collaborator_yaml_dir)
        raise typer.Exit()
    elif load_agents_only and update_tool is not None:
        raise ValueError(
            "Invalid argument combination: [--load_agents_only, --update_tool]. Must be used with --domain or --manager."
        )

    manager_path: Optional[Path] = None
    if manager:
        # If path, then will just return the path, else find the path tied to the tag.
        manager_path = TagToManagerMapper().get_manager_path_from_tag(str(manager))

    if update_tool:
        # Build the tools map.
        tools_mapper = ToolsDataMap()
        if not tools_mapper.get_tool_by_name(update_tool):
            raise KeyError(f"Tool name not found: {update_tool}")
        manager_ids = ["UPDATE_TOOL"]
        targeted_tools = [update_tool]

    elif manager_path:
        manager_id, targeted_tools = AgentYamlsData(
            manager_filepath=manager_path
        ).get_tool_dependencies()
        manager_ids = [manager_id]

    elif domain:
        domain_managers = get_domain_managers(
            domain=domain, collaborator_yaml_dir=collaborator_yaml_dir
        )
        targeted_tools = []
        for domain_manager in domain_managers:
            manager_id, manager_targeted_tools = AgentYamlsData(
                manager_filepath=domain_manager
            ).get_tool_dependencies()
            targeted_tools.extend(manager_targeted_tools)
            manager_ids.append(manager_id)

    _, targeted_conn_id_map = ConnectionManager(
        force_conns_import=force_import_connections
    ).configure_connections_for_tools(
        targeted_tools=targeted_tools,
        resume_import=resume_import,
    )

    if not json_creds_file.exists():
        LOGGER.info("Loading tools with connections")

    if resume_import:
        # Get the loaded tools by name, then filter the targeted_conn_id_map
        tool_controller = ToolsController()
        loaded_tools = set(tool_controller.get_all_tools().keys())

        targeted_conn_id_map = {
            k: v for k, v in targeted_conn_id_map.items() if k not in loaded_tools
        }

    if mock_eval:
        eval_patch_tools_import(
            requirements_file_path=requirements_file,
            targeted_conn_id_map=targeted_conn_id_map,
            target_snapshot=mock_eval,
        )
    else:
        multi_file_tool_import(
            requirements_file_path=requirements_file,
            targeted_conn_id_map=targeted_conn_id_map,
        )

    if not update_tool:
        import_agents(
            collaborator_yaml_dir=collaborator_yaml_dir,
            domain=domain,
            manager=manager_path,
        )


if __name__ == "__main__":
    app()
