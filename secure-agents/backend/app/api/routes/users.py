from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.models import UserPublic

router = APIRouter()


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user information from IBM Verify token.

    User management is handled by IBM Verify, so this endpoint
    only returns the user information extracted from the JWT token.
    """
    return current_user
