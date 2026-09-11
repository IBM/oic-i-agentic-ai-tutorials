from agent_ready_tools.utils.sql_utils import clean_where_clause, format_where_input_string


def test_like_operator() -> None:
    """Verifies that the `clean_where_clause` function adds single quotes where needed for the
    special case of LIKE operator."""
    # Define test data and expected output:
    where_clause_basic = "Name LIKE %Eat% Limit 5"
    where_clause_no_percent = "Name LIKE Eat Limit 5"
    where_clause_single = "Name LIKE '%Eat%' Limit 5"
    where_clause_double = 'Name LIKE "%Eat%" Limit 5'
    expected_output_simple = "Name LIKE '%Eat%' Limit 5"

    where_clause_advanced = "(CaseNumber = 00001004 OR CaseNumber = 00008002) AND Name LIKE %Eat% AND State = OR AND CreatedDate>=2025-06-01T00:00:00Z LIMIT 5"
    expected_output_advanced = "(CaseNumber = '00001004' OR CaseNumber = '00008002') AND State = 'OR' AND CreatedDate >= 2025-06-01T00:00:00Z LIMIT 5"

    where_clase_name_and = (
        "SELECT Id, Name, Industry FROM Account WHERE Name=Express Logistics and Transport Test"
    )
    expected_where_clause_advanced_and = (
        "SELECT Id, Name, Industry FROM Account WHERE Name = 'Express Logistics and Transport Test'"
    )

    # Generate cleaned up where clause
    result_no_percent = clean_where_clause(where_clause_no_percent)
    result_single = clean_where_clause(where_clause_single)
    result_double = clean_where_clause(where_clause_double)
    result_basic = clean_where_clause(where_clause_basic)
    result_advanced = clean_where_clause(where_clause_advanced)
    result_and = clean_where_clause(where_clase_name_and)

    # Run Unit Tests
    assert result_no_percent == expected_output_simple
    assert result_single == expected_output_simple
    assert result_double == expected_output_simple
    assert result_basic == expected_output_simple
    assert result_advanced == expected_output_advanced
    assert result_and == expected_where_clause_advanced_and


def test_clean_where_clause_single_entry() -> None:
    """Verifies that the `clean_where_clause` function adds single quotes to string values."""

    # Define test data:
    where_clause = "AcccountId=001fJ00000223n6QAA"
    expected_output = "AcccountId = '001fJ00000223n6QAA'"

    where_clause_single = "(AcccountId='001fJ00000223n6QAA' OR LeadSource =Trade Show)"
    where_clause_double = 'AcccountId = "001fJ00000223n6QAA"'

    result_single = clean_where_clause(where_clause_single)
    result_double = clean_where_clause(where_clause_double)
    result = clean_where_clause(where_clause)

    assert result_single == "(AcccountId = '001fJ00000223n6QAA' OR LeadSource = 'Trade Show')"
    assert result_double == expected_output
    assert result == expected_output


def test_clean_where_clause() -> None:
    """Verifies that the `clean_where_clause` function adds single quotes to string values."""

    # Define test data:
    where_clause = "(LeadSource=Public Relations OR LeadSource=Trade Show)"
    expected_output = "(LeadSource = 'Public Relations' OR LeadSource = 'Trade Show')"
    result = clean_where_clause(where_clause)

    assert result == expected_output


def test_format_where_input_string() -> None:
    """Verifies `format_where_input_string` return proper string."""

    # Define test data:
    empty_where_clause = " "
    expected_empty = ""

    result_empty = format_where_input_string(empty_where_clause)

    assert result_empty == expected_empty
