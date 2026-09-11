from import_utils.tool_importer.agent_yamls_data import AgentYamlsData

ENTRYPOINT_MANAGER_NAME = "entrypoint_manager"

TEST_YAML_DATA = {
    # Should be ignored
    "excluded_manager": {
        "collaborators": ["missing_agent", "agent_one", "excluded_agent_one"],
        "tools": [],
        "filepath": "./collaborator_agents/test/excluded_manager.yaml",
    },
    "excluded_agent_one": {
        "collaborators": [],
        "tools": [
            "find_accounts_by_name",
            "list_account_contacts",
        ],
        "filepath": "./collaborator_agents/test/excluded_agent_one.yaml",
    },
    # Target manager agent
    "entrypoint_manager": {
        "collaborators": ["agent_one", "agent_two", "agent_three", "agent_four"],
        "tools": [],
        "filepath": "./collaborator_agents/test/entrypoint_manager.yaml",
    },
    "agent_one": {
        "collaborators": ["agent_five"],
        "tools": ["search_company_by_criteria", "search_company_by_typeahead"],
        "filepath": "./collaborator_agents/test/agent_one.yaml",
    },
    "agent_two": {
        "collaborators": [],
        "tools": ["get_generative_search_sources", "get_generative_search"],
        "filepath": "./collaborator_agents/test/agent_two.yaml",
    },
    "agent_three": {
        "collaborators": [],
        "tools": ["get_industry_profile", "get_news_and_media"],
        "filepath": "./collaborator_agents/test/agent_three.yaml",
    },
    "agent_four": {
        "collaborators": [],
        "tools": ["send_email"],
        "filepath": "./collaborator_agents/test/agent_four.yaml",
    },
    "agent_five": {
        "collaborators": [],
        "tools": ["get_company_data", "search_company_by_typeahead"],
        "filepath": "./collaborator_agents/test/agent_five.yaml",
    },
}


def test_search_for_collaborators() -> None:
    """Test the recursive search for collaborators an topological building."""
    # Arrange
    agent_obj = AgentYamlsData.__new__(AgentYamlsData)
    agent_obj.entrypoint_manager_name = ENTRYPOINT_MANAGER_NAME
    agent_obj.yaml_data = TEST_YAML_DATA

    # Act
    topological_order = agent_obj._build_topological_order()  # pylint: disable=protected-access

    # Assert
    expected_topological_order = [
        "agent_five",
        "agent_four",
        "agent_three",
        "agent_two",
        "agent_one",
        "entrypoint_manager",
    ]
    assert (
        topological_order == expected_topological_order
    ), f"\nActual:   {", ".join(topological_order)}\nExpected: {", ".join(expected_topological_order)}"


def test_get_tools_dependencies() -> None:
    """Test the fetching of all tools dependencies."""
    # Arrange
    agent_obj = AgentYamlsData.__new__(AgentYamlsData)
    agent_obj.entrypoint_manager_name = ENTRYPOINT_MANAGER_NAME
    agent_obj.yaml_data = TEST_YAML_DATA

    # Act
    _, tools_deps = agent_obj.get_tool_dependencies()

    # Assert
    actual_tools_deps = set(tools_deps)
    expected_tools_deps = {
        "get_company_data",
        "get_news_and_media",
        "send_email",
        "get_generative_search_sources",
        "get_industry_profile",
        "search_company_by_typeahead",
        "get_generative_search",
        "search_company_by_criteria",
    }

    failure_out_actual = sorted(list(actual_tools_deps))
    failure_out_expected = sorted(list(expected_tools_deps))
    assert (
        actual_tools_deps == expected_tools_deps
    ), f"\nActual:   {", ".join(failure_out_actual)}\nExpected: {", ".join(failure_out_expected)}"
