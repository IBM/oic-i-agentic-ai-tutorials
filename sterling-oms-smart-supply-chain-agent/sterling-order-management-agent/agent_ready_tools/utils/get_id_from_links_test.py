from agent_ready_tools.utils.get_id_from_links import get_id_from_links, get_query_param_from_links


def test_get_id_from_links() -> None:
    """Verifies that the `get_id_from_links` function splits the id from the href."""

    # Define test data:
    test_data = {
        "assignment_id": "00020000000EACED00057708000110D932850CD80000004AAC",
        "worker_id": "00020000000EACED00057708000110D932471E0F0000004AAC",
        "url": "https://test.oraclecloud.com:443/hcmRestApi/resources/11.13.18.05",
    }

    result = get_id_from_links(
        f"{test_data['url']}/workers/{test_data['worker_id']}/child/addresses/{test_data['assignment_id']}"
    )

    assert result == test_data["assignment_id"]


def test_get_query_param_from_links() -> None:
    """Verifies that the `get_query_param_from_links` function extracts query parameters
    correctly."""

    # Define test data:
    url = "https://graph.microsoft.com/v1.0/me/contactFolders?$top=100&$skip=100"
    expected_params = {
        "$top": "100",
        "$skip": "100",
    }
    result = get_query_param_from_links(url)

    assert result == expected_params
