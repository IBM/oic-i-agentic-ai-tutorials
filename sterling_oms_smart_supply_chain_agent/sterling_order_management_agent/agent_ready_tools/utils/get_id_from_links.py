import re
from typing import Any
from urllib.parse import parse_qs, urlparse


def get_id_from_links(href: str) -> str:
    """
    Splits the ID from the href of the get tools in Oracle HCM.

    Args:
        href (str): The URL from which to extract the ID.

    Returns:
        str: The extracted ID.
    """
    href_list = re.split(r"([^\/]+)$", href)  # splits the href based on the last instance of '/'
    unique_id = href_list[1]

    return unique_id


def get_query_param_from_links(href: str) -> dict[str, Any]:
    """
    Extracts query parameters from a given URL.

    Args:
        href (str): The URL from which to extract query parameters.

    Returns:
        dict[str, Any]: A dictionary containing the query parameters as keys and their values as string.
    """
    if href:
        parsed_url = urlparse(href)
        query_params = {key: value[0] for key, value in parse_qs(parsed_url.query).items()}
    else:
        query_params = {}

    return query_params
