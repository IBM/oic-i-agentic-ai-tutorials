from enum import Enum
import json
from typing import Any, List, Type, TypeVar, Union

T = TypeVar("T", bound=Enum)


def string_to_list_of_strings(input_string: str) -> List[str]:
    """
    Some tools take a string from an LLM output which can have two formats:

    1) "foo"
    2) "['foo', 'bar', 'baz']"

    Convert this input to a list of strings.

    Args:
        input_string: "['foo', 'bar', 'baz']" or "foo"

    Returns:
        A python list of strings, i.e. ["foo", "bar", "baz"] or ["foo"]
    """
    if input_string.startswith("[") and input_string.endswith("]"):
        # Convert quotes as json does cannot handle '"' format
        return json.loads(input_string.replace("'", '"'))
    return [input_string]


def string_to_list_of_enums(input_string: str, enum_class: Type[T]) -> List[T]:
    """
    Some tools take a string from an LLM output which can have two formats:

    1) "foo"
    2) "['foo', 'bar', 'baz']"

    Convert this input to a list of enums.

    Args:
        input_string: "['foo', 'bar', 'baz']" or "foo"
        enum_class: the enum class to convert to

    Returns:
        A python list of enums, i.e. [MyClass.foo, MyClass.bar, MyClass.baz] or [MyClass.foo]
    """
    # TODO: Handle possibility that LLM hallucainates a non Enum string, add backoff logic to recover from KeyError.
    return [enum_class[s] for s in string_to_list_of_strings(input_string)]


def string_to_list_of_ints(value: Union[str, list[int]]) -> list[int]:
    """
    Convert a comma-separated string or list to a list of integers.

    Args:
        value: A string (e.g. "1,2,3") or list of ints.

    Returns:
        A list of integers parsed from the input.
    """
    if isinstance(value, list):
        return value
    if isinstance(value, str):

        try:
            parsed = json.loads(value)
            if isinstance(parsed, list) and all(isinstance(i, int) for i in parsed):
                return parsed
            elif isinstance(parsed, int):
                return [parsed]
        except json.JSONDecodeError:
            pass

        if value.strip().isdigit():
            return [int(value.strip())]
        return [int(v.strip()) for v in value.split(",") if v.strip().isdigit()]
    raise ValueError("Invalid input type for string_to_list_of_ints")


def string_to_boolean(value: str) -> bool:
    """
    Convert a string to a boolean.

    Args:
        value: A string (e.g. "true" or "false").

    Returns:
        A boolean parsed from the input.
    """

    if isinstance(value, str):
        value = value.strip().lower()
        if value == "true":
            return True
        elif value == "false":
            return False
    return False


def is_empty_value(value: Any) -> bool:
    """
    Checks whether the given value is empty.

    Args:
        value: The value to check. Can be of any type.

    Returns:
        True if the value is None, null, an empty string, an empty list, or an empty dictionary; False otherwise.
    """
    return value in (None, "null", "", [], {})
