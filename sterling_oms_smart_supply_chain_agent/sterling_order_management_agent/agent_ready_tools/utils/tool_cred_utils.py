from enum import StrEnum
from typing import Optional, Type

from agent_ready_tools.utils.systems import Systems


class InvalidConnectionSubCategoryError(ValueError):
    """Exception raised when a given system sub_category is invalid."""

    def __init__(
        self, system: Systems, sub_category: Optional[str], sub_category_enum: Type[StrEnum]
    ):
        """Initialize as ValueError with specific str."""
        super().__init__(
            f"Invalid sub_category for {system} connections: {sub_category}. Must be one of: {list(sub_category_enum)}"
        )


class UnsupportedConnectionSubCategoryError(ValueError):
    """Exception raised when a given (valid) system sub_category has no defined connections."""

    def __init__(self, system: Systems, sub_category: Optional[str]):
        """Initialize as ValueError with specific str."""
        super().__init__(f"Unsupported sub_category for {system} connections: {sub_category}")
