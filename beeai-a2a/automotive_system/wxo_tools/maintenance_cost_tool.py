from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

@tool(name="check_maintenance_cost", permission=ToolPermission.READ_ONLY)
def check_maintenance_cost(component: str, days_left: int) -> dict:
    est_cost = 250 if component == "Brake Pads" else 400
    recommended = days_left < 8
    return {"component": component, "estimated_cost": est_cost, "recommended": recommended}
