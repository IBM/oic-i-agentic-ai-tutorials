from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

@tool(
    name="check_maintenance_cost",
    description="Estimate maintenance cost for a component",
    permission=ToolPermission.READ_ONLY
)
def check_maintenance_cost(component: str, failure_in_days: int, vehicle_id: str = None) -> dict:
    """
    Estimate cost based on component and urgency.
    
    Args:
        component: Component name (from predict_vehicle_failure)
        failure_in_days: Days until failure (from predict_vehicle_failure)
        vehicle_id: Vehicle ID (passed through)
    """
    est_cost = 250 if component == "Brake Pads" else 400
    recommended = failure_in_days < 8
    
    return {
        "vehicle_id": vehicle_id,  # Pass through
        "component": component,  # Pass through
        "failure_in_days": failure_in_days,  # Pass through
        "estimated_cost": est_cost,
        "recommended": recommended
    }