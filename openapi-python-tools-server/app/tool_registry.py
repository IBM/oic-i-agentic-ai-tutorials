from app.models import ToolCatalog, ToolDescriptor


TOOLS = [
    ToolDescriptor(
        name="compute_integral",
        method="POST",
        path="/tools/math/integral",
        operation_id="compute_integral",
        description="Compute a definite integral for a safe allow-list of math functions.",
    ),
    ToolDescriptor(
        name="extract_text_insights",
        method="POST",
        path="/tools/text/insights",
        operation_id="extract_text_insights",
        description="Return word count, sentence count, and top keywords for a text block.",
    ),
    ToolDescriptor(
        name="score_customer_priority",
        method="POST",
        path="/tools/customer/priority",
        operation_id="score_customer_priority",
        description="Score a customer signal and recommend the next action.",
    ),
]


def get_tool_catalog() -> ToolCatalog:
    return ToolCatalog(tools=TOOLS)
