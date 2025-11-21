import random
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

@tool(
    name="predict_vehicle_failure",
    description="Dummy ML predictor that forecasts brake-pad failure window.",
    permission=ToolPermission.READ_ONLY
)
def predict_vehicle_failure(vehicle_id: str) -> dict:
    prediction_days = random.randint(5, 12)
    return {
        "vehicle_id": vehicle_id,
        "component": "Brake Pads",
        "failure_in_days": int(prediction_days),
        "confidence": 0.85
    }
