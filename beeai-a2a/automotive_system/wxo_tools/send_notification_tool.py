from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

@tool(name="notify_driver", permission=ToolPermission.WRITE)
def notify_driver(driver_id: str, message: str) -> dict:
    # In production: send SMS/Push/Email. Here we return success for tutorial.
    return {"sent": True, "driver_id": driver_id, "message": message}
