import functools
import inspect
from typing import Any, Callable, Dict, Type

from agent_ready_tools.utils.env import in_pants_env

# Single entry of the most recent api data.
captured_api_data: Dict[str, Any] = {}


TOOLS_RUNTIME_MOCK_DATA_PATH = "agent_ready_tools/mock_data"


def get_captured_api_data() -> Dict[str, Any]:
    """
    Accessor for the global captured api data.

    Returns:
        Dict[str, Any]: The global captured api data.
    """
    assert captured_api_data
    return captured_api_data


def set_captured_api_data(api_data: Dict[str, Any]) -> None:
    """
    Setter for global captured api data.

    Args:
        api_data (Dict[str, Any]): From the decorator, assign the captured api data.
    """
    global captured_api_data  # pylint: disable=global-statement
    captured_api_data = api_data


def reset_captured_api_data() -> None:
    """Reset back to empty."""
    global captured_api_data  # pylint: disable=global-statement
    captured_api_data = {}


def capture_api_public_fn() -> Callable:
    """
    Decorator factory that captures api calls and builds out a reference using the mocked data
    format for plug and play support for our existing mocked client code. Will save the code in a
    global object for an outer script to use.

    Returns:
        The api original results. We only capture and save the results so we can call back the values later.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:

            # Call the original function
            result = func(*args, **kwargs)

            if not in_pants_env():
                return result

            # Get the calling tool and argument
            caller_frame_info = inspect.stack()[1]
            caller_frame = caller_frame_info.frame
            arg_info = inspect.getargvalues(caller_frame)

            captured_api_response = {
                # "client_method": func.__name__,  # TODO: let's add this to reduce collisions, but verify base expectations WAI
                "args": {arg_name: arg_info.locals[arg_name] for arg_name in arg_info.args},
                "tool_name": caller_frame_info.function,
                "optional_args": {},
                "tool_output": None,  # Need to fill in outer scope. For validation use.
                "json_output": result,
            }
            set_captured_api_data(captured_api_response)

            return result

        return wrapper

    return decorator


def capture_api(*args: Any, **kwargs: Any) -> Callable:
    """
    Class decorator that wraps all public methods of a class with the mock_fcn_data decorator so
    that they return mock data based on a predefined list of mappings.

    Args:
        *args: passthrough of arguments for class init.
        **kwargs: passthrough of keyword arguments for class init.

    Returns:
        A class decorator that wraps public methods to return mock data.
    """

    def class_wrapper(cls: Type[Any], *args: Any, **kwargs: Any) -> Type[Any]:
        # {function_name: function} mapping
        for attr_name, attr_value in cls.__dict__.items():
            # wrapper around user methods only
            if callable(attr_value) and not attr_name.startswith("_"):
                decorator = capture_api_public_fn()(attr_value)
                setattr(cls, attr_name, decorator)
        return cls

    return class_wrapper(*args, **kwargs)
