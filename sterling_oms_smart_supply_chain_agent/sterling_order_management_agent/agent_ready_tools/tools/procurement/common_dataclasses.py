from typing import Generic, Optional, TypeVar

from pydantic.dataclasses import dataclass

T = TypeVar("T")


@dataclass
class ToolResponse(Generic[T]):
    """A unified wrapper for all of the tool responses."""

    success: bool
    message: str
    content: Optional[T] = None
    content_details: Optional[T] = None
