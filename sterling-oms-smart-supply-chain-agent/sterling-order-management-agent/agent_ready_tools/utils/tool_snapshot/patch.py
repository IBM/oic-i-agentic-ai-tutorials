from contextlib import contextmanager
import enum
from functools import wraps
import importlib
import inspect
from pathlib import Path
import types
from typing import Any, Callable, Optional
from unittest.mock import patch

import ibm_watsonx_orchestrate.agent_builder.tools


class PatchMode(enum.Enum):
    """Enums for modes of Patching."""

    PASSTHROUGH = enum.auto()
    REPLAY = enum.auto()
    CAPTURE = enum.auto()


def patch_tool_id(
    *, tool_name: str, tool_kwargs: Optional[dict[str, Any]] = None
) -> Callable[..., Any]:
    """
    Decorator for the test data to identify which "fixture" function goes with which tool.

    Args:
        tool_name: Name of the tool to patch.
        tool_kwargs: Keyword arguments that are passed to the tool.

    Returns:
        The decorated function containing the patch data.
    """

    def decorator(func: Callable) -> Callable[..., Any]:
        """
        Decorator for adding metadata to function for mapping of tool call and args to a patch func.

        Args:
            func: Function to patch.

        Returns:
            Wrapped function with extra metadata.
        """

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """
            Wrapper that allows for arbitrary attributes to be added.

            Args:
                args: Positional arguments passed to the function.
                kwargs: Keyword arguments passed to the function.

            Returns:
                Wrapped patch "fixtures"
            """
            return func(*args, **kwargs)

        # Identify the function that is specifically decorated by this deco.
        setattr(wrapper, "__patch_decorated__", True)

        # Bind data to function defn attributes for mapping to the proper "fixture" function.
        setattr(wrapper, "tool_name", tool_name)
        setattr(wrapper, "tool_kwargs", tool_kwargs if tool_kwargs else {})

        return wrapper

    return decorator


def _dynamically_import_patch_data(patch_data_filepath: str) -> types.ModuleType:
    """
    Dynamically import the patch data module and return for binding with tool patcher.

    Args:
        patch_data_filepath (str): Path to the patch data file

    Returns:
        Module object of patch data file.
    """

    # Generate a python importable path from a filepath
    patch_data_path_parts = Path(patch_data_filepath).with_suffix("").parts
    # In case a full path is provided, find the relative path
    tools_idx = patch_data_path_parts.index("agent_ready_tools")
    trimmed_list = patch_data_path_parts[tools_idx:]
    module_path = ".".join(trimmed_list)

    return importlib.import_module(module_path)


def match_kwargs(fn_obj: Callable, tool_kwargs: dict[str, Any]) -> bool:
    """
    Loose matching of kwargs between an agent's tool call and the decorated fixtures arguments. Will
    search if the decorated kwargs are in the tool call.  Any non-defined kwargs will be ignored. If
    no decorated kwargs are defined, then just accept any tool call kwargs.

    Args:
        fn_obj: Fixture function definition
        tool_kwargs: Kwargs from the agent's tool call

    Returns:
        True if matching or no kwargs defined in decorator
    """

    # If fixture function not tagged with any kwarg requirements, consider it a match.
    if hasattr(fn_obj, "tool_kwargs") and not fn_obj.tool_kwargs:
        return True

    # Do a loose search for tool_call kwargs that matches the requirements.
    # Any extra kwargs from the tool_call can be ignored.
    fixture_kwargs = list(fn_obj.tool_kwargs.items()) if hasattr(fn_obj, "tool_kwargs") else []
    return all(kwargs_tuple in set(tool_kwargs.items()) for kwargs_tuple in fixture_kwargs)


def find_patched_function(
    patch_data_module: types.ModuleType, tool_name: str, tool_kwargs: dict[str, Any]
) -> Callable:
    """
    Search through all functions in a specific module and find the func decorated for patch replay.

    Matching based on tool_name and tool_kwargs. Any args are bound to its corresponding kwarg.

    Args:
        patch_data_module (types.ModuleType): The patch data module
        tool_name (str): Name of the tool to patch
        tool_kwargs (dict[str, Any]): Keyword arguments that are passed to the tool.

    Returns:
        Response generator function in the patch data that matches the parameters.
    """

    # inspect.getmembers() does not guarantee to the order they appear in the source code.
    # Sort functions to set priority of fixtures with kwargs requirement first over one without.
    decorated_fn_obj = [
        fn
        for _, fn in inspect.getmembers(patch_data_module)
        if callable(fn) and bool(getattr(fn, "__patch_decorated__", False))
    ]
    decorated_fn_obj.sort(key=lambda fn: len(getattr(fn, "tool_kwargs", None) or {}), reverse=True)

    for fn_obj in decorated_fn_obj:
        if fn_obj.tool_name == tool_name and match_kwargs(fn_obj, tool_kwargs):
            return fn_obj

    raise KeyError(
        f"No matching patch function. \ntool_name: {tool_name} \ntool_kwargs: {tool_kwargs}"
    )


def patched_call_func(patch_data_filepath: str) -> Callable[..., Any]:
    """
    Patch __call__ function while binding it with the patch data file.

    Args:
        patch_data_filepath: Patch data module filepath giving access to the wrapper through scoping.

    Returns:
        Callable function to replace the PythonTool.__call__ function.
    """

    def _call_replacement(self: Any, *args: Any, **kwargs: Any) -> Any:
        """
        Wrapped call with arguments to match the original `__call__` function.

        Taken this approach so it can bind to the `patch_data_module` that was dynamically imported
        without affecting the arg signature.

        Args:
            self: argument for usage in original class we are replacing.
            args: args for the original `__call__` function.
            kwargs: kwargs for the original `__call__` function.

        Returns:
            New patched function that is dynamically found in `patch_data_module`.
        """

        patch_data_module = _dynamically_import_patch_data(patch_data_filepath)
        tool_name = self.fn.__name__
        # Map the positional arguments to kwargs based on the function arg signature.
        sig = inspect.signature(self.fn)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        tool_kwargs = dict(bound_args.arguments)

        patched_data_fn = find_patched_function(
            patch_data_module=patch_data_module, tool_name=tool_name, tool_kwargs=tool_kwargs
        )

        return patched_data_fn(*args, **kwargs)

    return _call_replacement


@contextmanager
def patch_python_tool_call_func(patch_data_filepath: str) -> Any:
    """
    Patch the PythonTool.__call__ return value to force a specific ToolResponse.

    Benefits:
    - Will work with any PythonTool decorated object.
    - Since a sandbox is isolated, no pollution between tool calls.
    - Simple injection: mutating a single point in call stack that is consistent across all tools.
    - We can also patch in any location of the tool file, not limited to after Tool fn has been interpreted.

    Cons:
    - No validation: If misconfigured, a tool call can return an unexpected result.
    - Misconfigured constraint is prevalent with any method we take. (Need to test Agent behavior)

    Args:
        patch_data_filepath (str): Filepath to collection of functions to build Responses for snapshot replay

    Returns:
        patcher object if action on object is needed
    """
    patched_func_with_data_path = patched_call_func(patch_data_filepath)

    patcher = patch.object(
        target=ibm_watsonx_orchestrate.agent_builder.tools.PythonTool,
        attribute="__call__",
        new=patched_func_with_data_path,
    )

    try:
        patcher.start()
        yield patcher
    finally:
        patcher.stop()


@contextmanager
def patch_expected_credentials() -> Any:
    """
    Patch PythonTool to ignore expected credentials and act as if no expected credentials were used.

    Returns:
        patcher object if action on object is needed
    """
    patcher = patch.object(
        target=ibm_watsonx_orchestrate.agent_builder.tools.python_tool,
        attribute="_parse_expected_credentials",
        return_value=[],
    )

    try:
        patcher.start()
        yield patcher
    finally:
        patcher.stop()
