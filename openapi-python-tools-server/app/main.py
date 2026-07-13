from fastapi import Depends, FastAPI, HTTPException, status

from app.models import (
    CustomerPriorityRequest,
    CustomerPriorityResponse,
    HealthResponse,
    IntegralRequest,
    IntegralResponse,
    TextInsightsRequest,
    TextInsightsResponse,
    ToolCatalog,
)
from app.security import require_api_key
from app.tool_registry import get_tool_catalog
from tools.customer_tools import score_customer_priority
from tools.math_tools import compute_integral
from tools.text_tools import extract_text_insights


secured_route = [Depends(require_api_key)]

app = FastAPI(
    title="Customer Python Tools API",
    version="0.1.0",
    description=(
        "Template service that exposes Python tool functions as OpenAPI operations."
    ),
    contact={"name": "Customer tools team"},
)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["system"],
    operation_id="get_health",
)
def get_health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get(
    "/tools",
    response_model=ToolCatalog,
    tags=["catalog"],
    operation_id="list_tools",
    dependencies=secured_route,
)
def list_tools() -> ToolCatalog:
    return get_tool_catalog()


@app.post(
    "/tools/math/integral",
    response_model=IntegralResponse,
    tags=["math"],
    operation_id="compute_integral",
    dependencies=secured_route,
)
def compute_integral_route(request: IntegralRequest) -> IntegralResponse:
    try:
        result = compute_integral(
            function_name=request.function_name,
            lower_bound=request.lower_bound,
            upper_bound=request.upper_bound,
            intervals=request.intervals,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return IntegralResponse(**result)


@app.post(
    "/tools/text/insights",
    response_model=TextInsightsResponse,
    tags=["text"],
    operation_id="extract_text_insights",
    dependencies=secured_route,
)
def extract_text_insights_route(
    request: TextInsightsRequest,
) -> TextInsightsResponse:
    return TextInsightsResponse(
        **extract_text_insights(
            text=request.text,
            max_keywords=request.max_keywords,
        )
    )


@app.post(
    "/tools/customer/priority",
    response_model=CustomerPriorityResponse,
    tags=["customer"],
    operation_id="score_customer_priority",
    dependencies=secured_route,
)
def score_customer_priority_route(
    request: CustomerPriorityRequest,
) -> CustomerPriorityResponse:
    return CustomerPriorityResponse(
        **score_customer_priority(
            customer_id=request.customer_id,
            tier=request.tier,
            open_support_tickets=request.open_support_tickets,
            days_since_last_contact=request.days_since_last_contact,
            contract_value_usd=request.contract_value_usd,
            recent_nps=request.recent_nps,
        )
    )
