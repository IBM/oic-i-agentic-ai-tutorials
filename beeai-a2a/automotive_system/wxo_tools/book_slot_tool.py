from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

@tool(name="book_service_slot", description="Book a vehicle service appointment slot and return confirmation with booking reference",permission=ToolPermission.READ_ONLY)
def book_service_slot(vehicle_id: str, slot: str) -> dict:
    # Dummy booking: always succeed
    return {"status": "confirmed", "slot": slot, "booking_ref": f"BOOK-{vehicle_id}-{slot.replace(':','-')}"}
