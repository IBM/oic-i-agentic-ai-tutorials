from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

@tool(
    name="order_parts",
    description="Order replacement parts for a component",
    permission=ToolPermission.READ_WRITE
)
def order_parts(component: str, vehicle_id: str = None, estimated_cost: int = None) -> dict:
    """
    Order parts for the specified component.
    
    Args:
        component: Component name (from previous steps)
        vehicle_id: Vehicle ID (passed through)
        estimated_cost: Cost estimate (passed through)
    """
    return {
        "vehicle_id": vehicle_id,  # Pass through
        "component": component,  # Pass through
        "status": "ordered",
        "order_id": f"ORD-{component.replace(' ', '-')}-001"
    }