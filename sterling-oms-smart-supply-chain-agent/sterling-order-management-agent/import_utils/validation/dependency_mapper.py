from dataclasses import dataclass
from pathlib import Path
import re
from typing import List, Optional, Set, Tuple

from import_utils.utils.directory import find_target_directory
from import_utils.utils.tools_data_mapper import ToolsDataMap
from rapidfuzz import process
import yaml


@dataclass
class YamlContentObject:
    """Class that defines the structure used to store the data from a processed yaml file."""

    agent_name_data: str
    instructions_data: str
    tools_data: List[str]


@dataclass
class DepMapperOutputObject:
    """Class that defines the structure for each object in the eventual dependency mapper output
    file."""

    agent_name: str
    external_agent_tools: List[str]
    internal_agent_tools: List[str]


def yaml_processor(file_path: Path) -> YamlContentObject:
    """
    Helper function that processes a yaml file to extract the information from the sections that
    contain the data needed to create an agent-to-tool dependency mapper.

    Args:
        file_path: Path to the file in relation to the module.

    Returns:
        The processed data in YamlContentObject form.
    """
    yaml_content_object: YamlContentObject = YamlContentObject(
        agent_name_data="", instructions_data="", tools_data=[]
    )

    with open(file_path, "r") as f:
        yaml_content_dict = yaml.safe_load(f)

        yaml_content_object.agent_name_data = yaml_content_dict["name"]
        yaml_content_object.instructions_data = yaml_content_dict["instructions"]
        yaml_content_object.tools_data = yaml_content_dict["tools"]

    return yaml_content_object


def instructions_tokenizer(tokens: List[str], instructions: str) -> Set[str]:
    """
    Tokenizes the list of existing tools in the repo against the corpus of tools listed in the
    instructions section of the yaml file.

    Args:
        tokens: List of existing tools in the repo that will be used as the tokens.
        instructions: The string of instructions section in the yaml.

    Returns:
        A set of all matches of tools.
    """
    # Rapidfuzz process extractOne takes a token (existing tool) to search for in a corpus (instructions)
    yaml_tools_word_set = set()

    instructions = re.sub(r"[\n]", "", instructions)  # Remove newline characters
    instructions = re.sub(
        r"[^a-zA-Z0-9\s_]", "", instructions
    )  # Remove any special characters that are not underscores (tool names involve underscores)
    instructions_list = instructions.split(" ")

    for tool in tokens:
        token_results = process.extractOne(tool, instructions_list)
        if token_results is not None and len(token_results) > 0:
            if token_results[1] == 100:  # only add the result if it had a 100% match
                yaml_tools_word_set.add(token_results[0])

    return yaml_tools_word_set


def agent_tool_dependency_mapper(parent_path: Optional[Path] = None) -> List[DepMapperOutputObject]:
    """
    Creates a dependancy map of agents and a list of tools they use.

    Args:
        parent_path: Parent path directory to search for.

    Returns:
        List of created dependency mapper output objects.
    """

    all_existing_tool_dict = ToolsDataMap().get_tool_name_to_tool_data_map()
    all_existing_tools_in_repo = list(all_existing_tool_dict.keys())

    json_output_content: List[DepMapperOutputObject] = []

    if parent_path is None:
        parent_path = find_target_directory("collaborator_agents")

    for root, _, files in parent_path.walk():
        for file in files:
            if file.endswith(".yaml") or file.endswith(".yml"):
                # process file contents
                module_path = Path(root) / file
                module_rel_path = module_path.relative_to(parent_path.parent)
                yaml_content_object = yaml_processor(module_rel_path)
                yaml_agent_name = yaml_content_object.agent_name_data
                yaml_instructions_data = yaml_content_object.instructions_data
                yaml_tools_data = yaml_content_object.tools_data

                # The helper function instructions_tokenizer returns what tools were found in the yaml instructions that also exist in the all_existing_tools_in_repo list
                yaml_instructions_tokenized_tool_data = instructions_tokenizer(
                    tokens=all_existing_tools_in_repo, instructions=yaml_instructions_data
                )

                # check if the tools that are mentioned in the instructions section of the yaml
                # are also listed in the tools section of the yaml (are they imported in this agent as a tool)
                # if they're not in the tools section then they are considered a dependancy from an external agent
                # essentially what we want to see is that there are no external tool dependencies
                int_agent_tools = []
                ext_agent_tools = []
                for tool in yaml_instructions_tokenized_tool_data:
                    if tool in yaml_tools_data:
                        int_agent_tools.append(tool)
                    else:
                        ext_agent_tools.append(tool)

                json_output_obj = DepMapperOutputObject(
                    agent_name=yaml_agent_name,
                    internal_agent_tools=int_agent_tools,
                    external_agent_tools=ext_agent_tools,
                )

                json_output_content.append(json_output_obj)

    return json_output_content


def _import_pycode_parser(
    target_dir: Path, import_pycode: str, full_import_context: bool = False
) -> Tuple[Path, Path]:
    """
    Helper function to build path from import line in py code. Try to match 2 patterns of importing.

    1. from package.module import object
    2. from package import module

    Args:
        target_dir: source to look for file
        import_pycode: import string line in py code
        full_import_context: Whether to consider "from" and "import" text together as part of
            filepath or not.

    Returns:
        from parsed import string, get abs file path of suspected file and rel path for archive
        building.
    """
    # Build path from import entry
    file_path_str = import_pycode.replace(".", "/").lstrip("from ")

    import_str_split = file_path_str.split(" import ")
    if full_import_context:
        # Ignore import aliases
        import_filename = import_str_split[1].split(" as ")[0]
        file_path_str = f"{import_str_split[0]}/{import_filename}.py"
    else:
        file_path_str = import_str_split[0] + ".py"
    rel_file_path = Path(file_path_str)

    # Pants sandbox in `agent_ready_tools` so remove first part of path built from import.
    tmp_rel_path = Path(*list(rel_file_path.parts)[1:])

    abs_file_path = (target_dir / tmp_rel_path).resolve()

    if not abs_file_path.exists():
        if full_import_context is False:
            return _import_pycode_parser(target_dir, import_pycode, full_import_context=True)
        else:
            raise FileNotFoundError(f"{str(abs_file_path)} does not exist")

    return abs_file_path, rel_file_path


def primitive_dependency_mapping(
    target_dir: Path, tool_py_filepath: Path
) -> List[Tuple[Path, Path]]:
    """
    Do a primitive dependency mapping by grepping the imports and recursively search through files.

    Aiming only at tools.

    Args:
        target_dir: Target directory to search for.
        tool_py_filepath: grep for deps and recursively check through children for deps

    Returns:
        manifest of dependencies.
    """

    import_list = []

    grep_for = "from agent_ready_tools."
    tool_reader = open(tool_py_filepath, "r")
    for line in tool_reader.readlines():
        if grep_for in line:
            import_list.append(line.strip())
    tool_reader.close()

    if not import_list:  # Recursion base case.
        return []

    dep_manifest = set()
    for import_pycode in import_list:
        abs_file_path, rel_file_path = _import_pycode_parser(target_dir, import_pycode)
        dep_manifest.add((abs_file_path, rel_file_path))

    dep_children = set()
    for abs_file_path, _ in dep_manifest:
        dep_dep_manifest = primitive_dependency_mapping(target_dir, abs_file_path)
        dep_children.update(dep_dep_manifest)  # can't change size of iter.
    dep_manifest.update(dep_children)

    return list(dep_manifest)


def general_init_builder(target_dir: Path, tool_py_abspath: Path) -> List[Tuple[Path, str]]:
    """
    Take a file at the end of a directory tree and build all __init__.py files in between arc root
    and target.

    Args:
        target_dir: Target directory to end init building at.
        tool_py_abspath: absolute path of tool python file to start at

    Returns:
        list of new arc path inits and empty string.
    """
    init_manifest = []
    tool_parent = tool_py_abspath.parent
    while tool_parent != target_dir.parent:
        init_manifest.append((tool_parent.relative_to(target_dir.parent) / "__init__.py", ""))
        tool_parent = tool_parent.parent
    return init_manifest


def build_dependency_init_manifest(
    target_dir: Path,
    dep_manifest: List[Tuple[Path, Path]],
) -> List[Tuple[Path, str]]:
    """
    For any dependency files, build the inits so importlib can find correct modules.

    Args:
        target_dir: Target directory to end init building at.
        dep_manifest: list of dependency file paths.

    Returns:
        list of init file paths and the custom strings to build for zip.
    """
    dep_init_manifest = []
    for abs_file_path, _ in dep_manifest:
        dep_init_manifest.extend(general_init_builder(target_dir, abs_file_path))
    return dep_init_manifest
