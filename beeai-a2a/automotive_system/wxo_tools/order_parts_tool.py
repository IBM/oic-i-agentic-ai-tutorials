from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

@tool(name="order_parts", description="Place an order for a vehicle component and return confirmation including ETA" ,permission=ToolPermission.READ_WRITE)
def order_parts(component: str) -> dict:
    # Dummy order response
    return {"ordered": True, "component": component, "eta_days": 3}
