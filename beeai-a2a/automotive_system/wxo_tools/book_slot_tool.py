from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

@tool(
    name="book_service_slot",
    description="Book a service appointment slot",
    permission=ToolPermission.READ_WRITE
)
def book_service_slot(vehicle_id: str, component: str = None, failure_in_days: int = None) -> dict:
    """
    Book service slot for the vehicle.
    
    Args:
        vehicle_id: Vehicle ID (from previous steps)
        component: Component needing service (passed through)
        failure_in_days: Urgency (passed through)
    """
    # Calculate slot based on urgency
    slot = "2025-11-22T15:00:00"
    
    return {
        "vehicle_id": vehicle_id,  # Pass through
        "component": component,  # Pass through
        "status": "confirmed",
        "slot": slot,
        "booking_ref": f"BOOK-{vehicle_id}-{slot.replace(':', '-')}"
    }