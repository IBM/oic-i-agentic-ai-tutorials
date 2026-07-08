import uuid
from typing import Any

from pydantic import EmailStr
from sqlmodel import Field, SQLModel

# IBM Verify User Info (from JWT token, not stored in database)


class UserPublic(SQLModel):
    """User information from IBM Verify JWT token"""

    id: str  # IBM Verify user ID (sub claim)
    email: EmailStr | None = None
    full_name: str | None = None
    preferred_username: str | None = None
    # Additional IBM Verify claims
    unique_name: str | None = None
    upn: str | None = None


# Token Info Response
class TokenInfoResponse(SQLModel):
    """Response model for token information"""

    is_valid: bool
    status_message: str
    header: dict[str, Any] | None = None
    payload: dict[str, Any] | None = None


# Feedback (formerly Items)
class FeedbackBase(SQLModel):
    feedback_type: str = Field(max_length=50)  # 'positive' or 'negative'
    feedback_comment: str | None = Field(default=None, max_length=1000)
    rated_message: str | None = Field(default=None, max_length=5000)
    user_message_before: str | None = Field(default=None, max_length=5000)


# Properties to receive on feedback creation
class FeedbackCreate(FeedbackBase):
    pass


# Properties to receive on feedback update
class FeedbackUpdate(SQLModel):
    feedback_type: str | None = Field(default=None, max_length=50)
    feedback_comment: str | None = Field(default=None, max_length=1000)
    rated_message: str | None = Field(default=None, max_length=5000)
    user_message_before: str | None = Field(default=None, max_length=5000)


class FeedbackPublic(FeedbackBase):
    id: uuid.UUID


class FeedbacksPublic(SQLModel):
    data: list[FeedbackPublic]
    count: int


# Backward compatibility aliases
ItemBase = FeedbackBase
ItemCreate = FeedbackCreate
ItemUpdate = FeedbackUpdate
ItemPublic = FeedbackPublic
ItemsPublic = FeedbacksPublic


## General


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)
