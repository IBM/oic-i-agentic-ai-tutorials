from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])


class ToolDescriptor(BaseModel):
    name: str
    method: str
    path: str
    description: str
    operation_id: str


class ToolCatalog(BaseModel):
    tools: list[ToolDescriptor]


class IntegralRequest(BaseModel):
    function_name: Literal["sin", "cos", "tan", "exp", "log", "sqrt"] = Field(
        ...,
        description="Math function to integrate.",
        examples=["sin"],
    )
    lower_bound: float = Field(..., examples=[0])
    upper_bound: float = Field(..., examples=[3.14159])
    intervals: int = Field(
        default=1000,
        ge=10,
        le=100000,
        description="Number of trapezoids used for numeric integration.",
    )


class IntegralResponse(BaseModel):
    result: float
    method: str
    intervals: int


class TextInsightsRequest(BaseModel):
    text: str = Field(..., min_length=1)
    max_keywords: int = Field(default=5, ge=1, le=20)


class Keyword(BaseModel):
    term: str
    count: int


class TextInsightsResponse(BaseModel):
    word_count: int
    sentence_count: int
    keywords: list[Keyword]


class CustomerPriorityRequest(BaseModel):
    customer_id: str = Field(..., min_length=1)
    tier: Literal["standard", "premium", "strategic"]
    open_support_tickets: int = Field(default=0, ge=0)
    days_since_last_contact: int = Field(default=0, ge=0)
    contract_value_usd: float = Field(default=0, ge=0)
    recent_nps: int | None = Field(default=None, ge=0, le=10)


class CustomerPriorityResponse(BaseModel):
    customer_id: str
    priority_score: int = Field(..., ge=0, le=100)
    priority: Literal["low", "medium", "high"]
    recommended_action: str
    reasons: list[str]
