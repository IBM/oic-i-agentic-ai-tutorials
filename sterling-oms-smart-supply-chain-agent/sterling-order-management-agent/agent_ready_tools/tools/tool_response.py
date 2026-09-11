from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, computed_field

from agent_ready_tools.clients.error_handling import ErrorDetails

T = TypeVar("T")


class ToolResponse(BaseModel, Generic[T]):
    """
    A unified wrapper for all tool responses, encapsulating either a successful output or error
    details if the tool failed.

    Attributes:
        error_details: Contains information about the error, if the tool failed.
        tool_output: The successful output of the tool, if any.

    Properties:
        is_success: Indicates whether the tool ran successfully (i.e., no error_details).

    Example:
        When the tool executes successfully, the ToolResponse will look like
        ToolResponse(is_success = True, error_details=None, tool_output=T(result="Hello, world!"))

        When the tool encounters an error while execution, the ToolResponse will look like
        ToolResponse(is_success = False, error_details=ErrorDetails(status_code=111, details="error"), tool_output=None)
    """

    error_details: Optional[ErrorDetails]
    tool_output: Optional[T]

    @computed_field  # type: ignore[misc]
    @property
    def is_success(self) -> bool:
        """Represents if the tool ran successfully."""
        return self.error_details is None
