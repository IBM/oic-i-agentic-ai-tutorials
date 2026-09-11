from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.core.db import engine
from app.core.security import decode_jwt_token
from app.models import UserPublic

# Use HTTPBearer for IBM Verify tokens
security_scheme = HTTPBearer()


def get_db() -> Generator[Session, None, None]:
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not configured for this deployment",
        )
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[HTTPAuthorizationCredentials, Depends(security_scheme)]


def get_current_user(token: TokenDep) -> UserPublic:
    """
    Extract user information from IBM Verify JWT token.
    No database lookup needed - user info comes from the token.
    """
    try:
        # Decode the IBM Verify token
        _, payload, error = decode_jwt_token(token.credentials)

        if error or not payload:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Could not validate credentials: {error}",
            )

        # Check token expiration
        import time

        exp = payload.get("exp")
        if exp and exp < time.time():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )

        # Extract user info from IBM Verify token
        user_info = UserPublic(
            id=payload.get("sub", ""),
            email=payload.get("unique_name") or payload.get("email"),
            full_name=payload.get("name"),
            preferred_username=payload.get("preferred_username"),
            unique_name=payload.get("unique_name"),
            upn=payload.get("upn"),
        )

        if not user_info.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token: missing user ID",
            )

        return user_info

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Could not validate credentials: {str(e)}",
        )


CurrentUser = Annotated[UserPublic, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> UserPublic:
    """
    Check if user is superuser based on IBM Verify groups or roles.
    You can customize this based on your IBM Verify configuration.
    """
    # For now, we'll check if the user's email is in a list of admin emails
    # You can modify this to check IBM Verify groups/roles from the token
    admin_emails = ["admin@example.com"]  # Configure this as needed

    if current_user.email not in admin_emails:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


CurrentSuperuser = Annotated[UserPublic, Depends(get_current_active_superuser)]
