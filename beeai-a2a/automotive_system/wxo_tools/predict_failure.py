import random
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

@tool(
    name="predict_vehicle_failure",
    description="Predict vehicle component failure and return details",
    permission=ToolPermission.READ_ONLY
)
def predict_vehicle_failure(vehicle_id: str) -> dict:
    """Predict when a vehicle component will fail."""
    prediction_days = random.randint(5, 12)
    return {
        "vehicle_id": vehicle_id,  # Pass through for later steps
        "component": "Brake Pads",
        "failure_in_days": prediction_days,
        "confidence": 0.85
    }