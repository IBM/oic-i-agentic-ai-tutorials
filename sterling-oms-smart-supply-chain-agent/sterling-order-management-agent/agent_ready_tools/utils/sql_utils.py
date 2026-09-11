import re
from typing import List, Match

# --- Constants ---
# Fields and operators that indicate a value should NOT be quoted.
DATE_FIELDS = {"createddate", "lastmodifieddate", "systemmodstamp"}
NUMERIC_OPERATORS = {">", "<", ">=", "<="}


def clean_where_clause(where_clause: str) -> str:
    """
    Cleans a SQL WHERE clause using a robust tokenizer and parser model.

    Args:
        where_clause: The SQL WHERE clause from an LLM to be cleaned.

    Returns:
        The cleaned up SQL where clause.
    """
    if not where_clause or not where_clause.strip():
        return ""

    # --- Pass 1: Handle LIMIT clause ---
    limit_clause = ""
    limit_match = re.search(r"\s+(LIMIT\s+\d+)$", where_clause, re.IGNORECASE)
    if limit_match:
        limit_clause = limit_match.group(0).strip()
        where_clause = where_clause[: limit_match.start()]

    # --- Pass 2: Protect all pre-quoted string literals with placeholders ---
    string_literals = []

    def protect_strings(match: Match[str]) -> str:
        string_literals.append(match.group(1))
        return f"__STR_{len(string_literals)-1}__"

    placeholder_clause = re.sub(r"'(.*?)'", protect_strings, where_clause)
    placeholder_clause = re.sub(r'"(.*?)"', protect_strings, placeholder_clause)

    # --- Pass 3: Recursively clean the structure ---
    cleaned_structure = _clean_structure_recursive(placeholder_clause, string_literals)

    # --- Final Step: Re-assemble ---
    if limit_clause:
        return f"{cleaned_structure} {limit_clause}"
    else:
        return cleaned_structure


def _process_condition(
    column: str, operator: str, value_str: str, string_literals: List[str]
) -> str:
    """Processes a single, structured condition to apply quoting."""
    is_string_placeholder = value_str.startswith("__STR_")
    should_be_quoted = is_string_placeholder or not (
        any(df in column.lower() for df in DATE_FIELDS)
        or operator.upper() in NUMERIC_OPERATORS
        or value_str.lower() in ["true", "false"]
        or _is_date_function(value_str)
    )

    value = value_str
    if should_be_quoted:
        if is_string_placeholder:
            index = int(value_str[len("__STR_") : -2])
            clean_value = string_literals[index].strip("'\"%").replace("'", "''")
        else:
            clean_value = value_str.strip("%").replace("'", "''")

        if operator.upper() == "LIKE":
            value = f"'%{clean_value}%'"
        else:
            value = f"'{clean_value}'"

    # Standardize spacing around the operator
    return f"{column} {operator.upper()} {value}"


def _is_date_function(value_str: str) -> bool:
    """Check if the value is a date function like DAY_ONLY(CreatedDate)."""
    return bool(re.match(r"\w+\(.*\)", value_str))


def _parse_and_rebuild(clause: str, string_literals: List[str], sub_clauses: List[str]) -> str:
    """Tokenizes and parses a simple clause (no parentheses) into a clean string."""
    if not clause:
        return ""

    # 1. Tokenizer: Breaks the clause into typed tokens.
    token_spec = [
        ("PLACEHOLDER", r"__SUB_\d+__|__STR_\d+__"),
        ("OPERATOR", r"[=><!]+|LIKE"),
        ("WORD", r"[\w\%\.\-:\@\&]+"),
        ("FUNCTION", r"\w+\([^)]+\)"),
        ("WHITESPACE", r"\s+"),
    ]
    tok_regex = "|".join(f"(?P<{name}>{pattern})" for name, pattern in token_spec)
    tokens = [
        mo for mo in re.finditer(tok_regex, clause, re.IGNORECASE) if mo.lastgroup != "WHITESPACE"
    ]

    # 2. Parser: Groups tokens into conditions using a more robust state-based rule.
    rebuilt_parts = []
    current_condition: List[Match[str]] = []
    i = 0

    while i < len(tokens):
        token = tokens[i]
        token_text = token.group().upper()

        # Check if this is a logical operator
        is_logical = token_text in ["AND", "OR"]

        if is_logical and len(current_condition) >= 2:
            # Look ahead to see if the next token looks like a column name
            # (i.e., the next token followed by an operator)
            next_is_column = False
            if i + 2 < len(tokens):
                next_token = tokens[i + 1]
                next_next_token = tokens[i + 2]
                if next_token.lastgroup == "WORD" and next_next_token.lastgroup == "OPERATOR":
                    next_is_column = True
            elif i + 1 < len(tokens):
                # Check if next token is a placeholder (sub-clause)
                next_token = tokens[i + 1]
                if next_token.lastgroup == "PLACEHOLDER" and next_token.group().startswith(
                    "__SUB_"
                ):
                    next_is_column = True

            if next_is_column:
                # This is actually a logical operator, finalize current condition
                rebuilt_parts.append(
                    _process_condition_tokens(current_condition, string_literals, sub_clauses)
                )
                rebuilt_parts.append(token_text)
                current_condition = []
            else:
                # This is part of the value, add it to current condition
                current_condition.append(token)
        else:
            # Add token to current condition
            current_condition.append(token)

        i += 1

    # Process the last condition after the loop
    if current_condition:
        rebuilt_parts.append(
            _process_condition_tokens(current_condition, string_literals, sub_clauses)
        )

    return " ".join(rebuilt_parts)


def _process_condition_tokens(
    tokens: List[Match[str]], string_literals: List[str], sub_clauses: List[str]
) -> str:
    """Rebuilds a clean string from a list of tokens representing one condition."""
    if not tokens:
        return ""

    token_text = tokens[0].group()
    if tokens[0].lastgroup == "PLACEHOLDER" and token_text.startswith("__SUB_"):
        index = int(token_text[len("__SUB_") : -2])
        return f"({sub_clauses[index]})"

    if len(tokens) >= 2 and tokens[1].lastgroup == "OPERATOR":
        column = tokens[0].group()
        operator = tokens[1].group()
        value_str = " ".join(t.group() for t in tokens[2:])
        return _process_condition(column, operator, value_str, string_literals)

    return " ".join(t.group() for t in tokens)


def _clean_structure_recursive(clause: str, string_literals: List[str]) -> str:
    """Recursively cleans a clause, handling parentheses and subqueries."""
    where_keyword_match = re.search(r"\s+WHERE\s+", clause, re.IGNORECASE)
    if where_keyword_match:
        pre_where_part = clause[: where_keyword_match.end()]
        post_where_part = clause[where_keyword_match.end() :]
        cleaned_post_where = _clean_structure_recursive(post_where_part, string_literals)
        return pre_where_part.strip() + " " + cleaned_post_where

    sub_clauses = []

    def protect_groups(match: Match[str]) -> str:
        cleaned_sub_clause = _clean_structure_recursive(match.group(1), string_literals)
        sub_clauses.append(cleaned_sub_clause)
        return f"__SUB_{len(sub_clauses)-1}__"

    # Use a more careful regex to avoid matching function calls
    placeholder_clause = re.sub(r"(?<!\w)\(([^()]*(?:\([^()]*\)[^()]*)*)\)", protect_groups, clause)

    cleaned_clause = _parse_and_rebuild(placeholder_clause, string_literals, sub_clauses)

    # Replace any remaining placeholders
    cleaned_clause = _replace_placeholders(cleaned_clause, string_literals, sub_clauses)

    return cleaned_clause


def _replace_placeholders(clause: str, string_literals: List[str], sub_clauses: List[str]) -> str:
    """Replace any remaining placeholders in the clause."""

    # Replace string placeholders
    def replace_string(match: Match[str]) -> str:
        index = int(match.group(1))
        if index < len(string_literals):
            return f"'{string_literals[index]}'"
        return match.group(0)

    clause = re.sub(r"__STR_(\d+)__", replace_string, clause)

    # Replace sub-clause placeholders
    def replace_sub(match: Match[str]) -> str:
        index = int(match.group(1))
        if index < len(sub_clauses):
            return f"({sub_clauses[index]})"
        return match.group(0)

    clause = re.sub(r"__SUB_(\d+)__", replace_sub, clause)

    return clause


def format_where_input_string(where_clause: str) -> str:
    """Cleans and formats a WHERE clause string."""
    if where_clause and where_clause.strip():
        return f"WHERE {clean_where_clause(where_clause)}"
    return ""
