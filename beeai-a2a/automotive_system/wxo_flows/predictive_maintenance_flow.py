from pydantic import BaseModel, Field
from ibm_watsonx_orchestrate.flow_builder.flows import flow, Flow, START, END
from wxo_tools.predict_failure import predict_vehicle_failure
from wxo_tools.maintenance_cost_tool import check_maintenance_cost
from wxo_tools.order_parts_tool import order_parts
from wxo_tools.book_slot_tool import book_service_slot
from wxo_tools.send_notification_tool import notify_driver


class MaintenanceInput(BaseModel):
    """Input schema for predictive maintenance flow."""
    vehicle_id: str = Field(description="Vehicle ID to check maintenance for")
    driver_id: str = Field(default="driver-1", description="Driver ID for notifications")


@flow(
    name="predictive_maintenance_flow",
    description="Predictive maintenance workflow that predicts failures, estimates costs, orders parts, books service, and notifies driver",
    schedulable=True,
    input_schema=MaintenanceInput
)
def build(aflow: Flow = None) -> Flow:
    """
    Predictive maintenance flow.
    Returns the complete output from notify_driver which includes:
    - sent, driver_id, message, booking_ref, summary
    """
    
    predict = aflow.tool(predict_vehicle_failure)
    cost = aflow.tool(check_maintenance_cost)
    order = aflow.tool(order_parts)
    book = aflow.tool(book_service_slot)
    notify = aflow.tool(notify_driver)
    
    aflow.sequence(START, predict, cost, order, book, notify, END)
    
    return aflow