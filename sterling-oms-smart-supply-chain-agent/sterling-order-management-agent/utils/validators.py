import datetime
import io
import os
from pathlib import Path
import re
from typing import Union
from xml.etree.ElementTree import ParseError

from svgelements import SVG

# This is a common library for standard validators.

Pathish = Union[str, Path]


def as_path(value: Pathish) -> Path:
    """
    Accept str or Path and return a clean Path with ~ and $VARS expanded.
    Args:
        p: The input path (string or Path object).

    Returns:
        A resolved Path object.
    """
    if isinstance(value, Path):
        return value.expanduser()
    return Path(os.path.expandvars(str(value))).expanduser()


VALID_SHORT_HASH_PATTERN = re.compile(r"^[0-9a-f]{4,40}$")
# A short Git hash is typically 7 characters long, but can vary.
# It must be composed of hexadecimal characters (0-9, a-f).
# This regex checks for 4 to 40 hexadecimal characters.
# Git defaults to 7 for --short, but can be longer if needed for uniqueness.
# The minimum length for abbreviation is 4.
# We'll allow up to 40 for cases where Git might need a longer "short" hash.


def is_short_git_hash(value: str) -> bool:
    """
    Validates if a string is a short Git hash.

    Args:
        value: The string to validate.

    Returns:
        True if the string is a short Git hash, False otherwise.
    """
    return bool(VALID_SHORT_HASH_PATTERN.match(value))


def is_iso_format(value: str) -> bool:
    """
    Validates if a given string is in ISO 8601 format.

    Args:
      value: The string to validate.

    Returns:
      True if the string is a valid ISO 8601 date/datetime, False otherwise.
    """
    try:
        datetime.datetime.fromisoformat(value)
        return True
    except ValueError:
        return False


def is_valid_svg_string(svg_string: str) -> bool:
    """
    Validates if a given string is valid SVG markup.

    Args:
        svg_string: The SVG string to validate.

    Returns:
        True if the string is valid SVG, False otherwise.
    """
    try:
        with io.StringIO(svg_string) as buffer:
            SVG.parse(buffer)
        return True
    except ParseError:
        return False
