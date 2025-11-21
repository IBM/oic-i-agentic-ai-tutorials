import requests
from pydantic import BaseModel, Field
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

class MaintenanceOutput(BaseModel):
    result: str = Field(description="The final maintenance recommendation text.")

@tool(
    name="predict_vehicle_maintenance",
    description="Call the BeeAI Predictive Maintenance A2A server and return the text result.",
    permission=ToolPermission.READ_ONLY
)
def predict_vehicle_maintenance(vehicle_id: str) -> MaintenanceOutput:
    """
    Calls the BeeAI A2A server locally and retrieves predictive maintenance results.
    """
    url = "http://127.0.0.1:9999"

    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "agent.run",
        "params": {
            "prompt": f"Predict maintenance for vehicle {vehicle_id}",
        },
    }

    response = requests.post(url, json=payload)
    response_json = response.json()

    # Extract returned text from BeeAI server JSON
    text = response_json["result"]["message"]["parts"][0]["text"]

    return MaintenanceOutput(result=text)
