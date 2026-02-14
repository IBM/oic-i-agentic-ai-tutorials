from beeai_framework.tools import tool

@tool(description="Get the current city for the given vehicle ID.")
def get_vehicle_location(vehicle_id: str):
    """Get vehicle location"""
    return {"vehicle_id": vehicle_id, "city": "San Francisco"}


@tool(description="Get the schedule availability for the driver.")
def get_driver_schedule(driver_id: str):
    """Get driver schedule"""
    return {"driver_id": driver_id, "availability": ["2025-11-22T14:00:00"]}


@tool(description="Get dealership service slots available in a given city.")
def get_dealership_slots(city: str):
    """Get dealership slots"""
    return {"city": city, "slots": ["2025-11-22T15:00:00"]}


@tool(description="Check inventory count for a specific vehicle component.")
def get_parts_inventory(component: str):
    """Check parts inventory"""
    return {"component": component, "stock": 5}


# Export all tools as a list
ALL_TOOLS = [
    get_vehicle_location,
    get_driver_schedule,
    get_dealership_slots,
    get_parts_inventory
]