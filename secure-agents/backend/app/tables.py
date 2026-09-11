import uuid

from sqlmodel import Field, SQLModel


# Feedback model
class Feedback(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    feedback_type: str = Field(max_length=50)  # 'positive' or 'negative'
    feedback_comment: str | None = Field(default=None, max_length=1000)
    rated_message: str | None = Field(
        default=None, max_length=5000
    )  # assistant message
    user_message_before: str | None = Field(default=None, max_length=5000)


# Keep Item as alias for backward compatibility during migration
Item = Feedback
