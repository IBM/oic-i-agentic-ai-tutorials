import logging
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)
logger.warning("...")


def get_index_value(input_obj: Any, index: int, default: Any = None) -> Any:
    """
    Returns value of item at specified index of an input object. Otherwise returns specified default
    value.

    Args:
        input_obj: The input object for which to conduct the length check and access the indexed value.
        index: The index the user would like to access.
        default: The default object to return if the length check is not passed.

    Returns:
        Either returns the specified default value, or the value of the object at the specified index.
    """

    try:
        assert input_obj
    except AssertionError:
        logger.warning("Warning Type Error: Empty object passed to get_index_value.")
        return default

    try:
        assert isinstance(input_obj, List)
    except AssertionError:
        logger.warning("Warning TypeError: Cannot index object during processing of api response.")
        return default

    try:
        return input_obj[index]
    except IndexError:
        logger.warning("Warning IndexError: Error indexing object when processing api response.")
        return default
    except TypeError:
        logger.warning("Warning TypeError: Cannot index object during processing of api response.")
        return default
    except ValueError:
        logger.warning(
            "Warning ValueError: Error indexing object when processing api response, invalid value type provided."
        )
        return default


def get_soap_value(resp_obj: Any, key_chain: str) -> Any:
    """
    A getter function that checks whether an attribute exists in a nested SOAP response object and
    retrieves the value. Otherwise returns a default value of None.

    Args:
        resp_obj: The whole nested SOAP api response object from which an attribute is being retrieved.
        key_chain: A string that describes the nested SOAP response object's structure, with all the attributes specified in the correct order.
            The last attribute listed is the value will be returned.
            e.x. "output.body.get_related_person.response_data.relationship"
            In the example, all of those attributes will be checked, and the value for the relationship attribute will be returned

    Returns:
        Either returns a default value of None, or the value of the last attribute listed in the key_chain input parameter.
    """
    try:
        assert resp_obj
    except AssertionError:
        logger.warning("TypeError, empty object passed to get_soap_value.")
        return None

    try:
        assert not isinstance(resp_obj, Dict)
    except AssertionError:
        logger.warning("TypeError, an api response object that is a SOAP response is expected.")
        return None

    try:
        assert isinstance(key_chain, str)
    except AssertionError:
        logger.warning("TypeError, a key chain that was not a string was passed.")
        return None

    _object = resp_obj
    attributes_to_check = key_chain.split(".")
    for attr_name in attributes_to_check:
        try:
            _object = getattr(_object, attr_name)
        except AttributeError:
            logger.warning(
                f"AttributeError: SOAP Object '{str(_object)}' doesn't have attribute '{attr_name}' where the root object is '{str(resp_obj)}'."
            )
            return None
    return _object


def get_rest_value(resp_obj: dict[Any, Any], key_chain: Union[str, List[str]]) -> Any:
    """
    A getter function that checks whether an attribute exists in a nested REST response object and
    retrieves the value. Otherwise returns a default value of None.

    Args:
        resp_obj: The whole nested SOAP api response object from which an attribute is being retrieved.
        key_chain: Either a single string (for one key), or a list of strings (for multiple keys) that describes the whole chain of keys of the nested REST response object's structure.
            All the keys must be specified in the correct order. If the correct order is not specified then the return will be a default of None.
            For multiple keys specified (a list of keys), the last key listed is the value that will be returned.
            e.x. multiple keys - ["output", "body", "get_related_person", "response_data", "relationship"]
            In the example above, all of those attributes will be checked, and the final value for the "relationship" key will be returned (if found, otherwise None).
            e.x. one key - "output"
            In the example above, only one string is specified, so only the value for the "output" key will be returned (if found, otherwise None).


    Returns:
        Either returns a default value of None, or the value of the last key listed in the key_chain input parameter (for multiple keys), or the value of the single key specified in the input parameter.
    """
    try:
        assert resp_obj
    except AssertionError:
        logger.warning("TypeError, empty object passed to get_rest_value.")
        return None

    try:
        assert isinstance(resp_obj, Dict)
    except AssertionError:
        logger.warning("TypeError, an api response object that is a REST response is expected.")
        return None

    try:
        assert isinstance(key_chain, (str, List))
    except AssertionError:
        logger.warning(
            "TypeError, a key chain that was not a list of strings, or a single string, was passed."
        )
        return None

    _object = resp_obj
    if isinstance(key_chain, str):
        key_chain = [key_chain]

    for key_name in key_chain:
        try:
            if _object:
                _object = _object.get(key_name)  # type: ignore[assignment]
        except (KeyError, AttributeError):
            logger.warning(
                f"KeyError: REST Object '{str(_object)}' doesn't have key '{key_name}' where the root object is '{str(resp_obj)}'."
            )
            return None
    return _object
