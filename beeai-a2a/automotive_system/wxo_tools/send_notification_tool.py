from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

@tool(
    name="notify_driver",
    description="Send notification to driver about maintenance",
    permission=ToolPermission.READ_WRITE
)
def notify_driver(
    driver_id: str,
    vehicle_id: str = None,
    component: str = None,
    failure_in_days: int = None,
    booking_ref: str = None
) -> dict:
    """
    Notify driver about scheduled maintenance.
    
    Args:
        driver_id: Driver ID (from flow input)
        vehicle_id: Vehicle ID (passed through)
        component: Component needing service (passed through)
        failure_in_days: Days until failure (passed through)
        booking_ref: Booking reference (from book_service_slot)
    """
    message = (
        f"Maintenance scheduled for {vehicle_id}. "
        f"{component} needs service in {failure_in_days} days. "
        f"Booking: {booking_ref}"
    )
    
    return {
        "sent": True,
        "driver_id": driver_id,
        "message": message,
        "booking_ref": booking_ref,
        "summary": (
            f"Vehicle {vehicle_id}: {component} maintenance booked "
            f"(Reference: {booking_ref})"
        )
    }