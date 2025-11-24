from pydantic import BaseModel, Field
from ibm_watsonx_orchestrate.flow_builder.flows import (
    flow, Flow, START, END
)
from predict_maintenance_tool import predict_vehicle_maintenance

class MaintenanceInput(BaseModel):
    vehicle_id: str = Field(description="Vehicle ID to check maintenance for.")

class MaintenanceOutput(BaseModel):
    result: str = Field(description="Maintenance results text.")

@flow(
    name="vehicle_maintenance_flow",
    schedulable=True,       # <-- IMPORTANT for Scheduler
    output_schema=MaintenanceOutput
)
def build_maintenance_flow(aflow: Flow = None) -> Flow:

    node = aflow.tool(predict_vehicle_maintenance)
    aflow.sequence(START, node, END)

    return aflow
