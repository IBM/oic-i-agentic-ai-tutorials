from ibm_watsonx_orchestrate.flow_builder.flows import flow, Flow, START, END

from predict_failure import predict_vehicle_failure
from maintenance_cost_tool import check_maintenance_cost
from order_parts_tool import order_parts
from book_slot_tool import book_service_slot
from send_notification_tool import notify_driver

@flow(name="predictive_maintenance_flow",description=(
        "Flow that sequences maintenance prediction, cost estimation, parts ordering, "
        "service slot booking, and driver notification for a vehicle."
    ), schedulable=True)
def build(aflow: Flow = None) -> Flow:
    predict = aflow.tool(predict_vehicle_failure)
    cost = aflow.tool(check_maintenance_cost)
    order = aflow.tool(order_parts)
    book = aflow.tool(book_service_slot)
    notify = aflow.tool(notify_driver)

    aflow.sequence(START, predict, cost, order, book, notify, END)
    return aflow
