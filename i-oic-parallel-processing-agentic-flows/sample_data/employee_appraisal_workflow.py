"""
Employee Appraisal Workflow - Optimized Parallel Processing with Download

This workflow:
1. Prompts user to upload employee data file
2. Reads all employee data
3. Processes each employee's appraisal in PARALLEL
4. Flattens results using helper tool (eliminates duplication)
5. Generates downloadable Excel file
6. Provides download button to user
7. Returns summary to agent
"""

from ibm_watsonx_orchestrate.flow_builder.flows import Flow, flow, START, END
from ibm_watsonx_orchestrate.flow_builder.types import ForeachPolicy, UserFieldKind, Assignment
from ibm_watsonx_orchestrate.flow_builder.data_map import DataMap
from pydantic import BaseModel, Field

# Import the tools (they must be imported before the workflow)
from .appraisal_tools import (
    read_employee_data,
    calculate_employee_appraisal,
    generate_appraisal_excel,
    EmployeeData,
    AppraisalResult
)


# ============================================================================
# WORKFLOW INPUT/OUTPUT SCHEMAS
# ============================================================================

class WorkflowInput(BaseModel):
    """Input schema for the workflow"""
    pass  # No input needed, file will be uploaded via user flow


class WorkflowOutput(BaseModel):
    """Output schema for the workflow"""
    total_employees_processed: int = Field(description="Total number of employees processed")
    results: list[AppraisalResult] = Field(description="List of appraisal results for all employees")
    message: str = Field(description="Success message with summary")
    download_file: bytes = Field(description="Excel file with appraisal results as downloadable bytes")


# ============================================================================
# WORKFLOW DEFINITION
# ============================================================================

@flow(
    name="employee_appraisal_parallel_workflow",
    description="Processes employee appraisals in parallel from uploaded Excel/CSV file with downloadable results",
    input_schema=WorkflowInput,
    output_schema=WorkflowOutput
)
def build_employee_appraisal_workflow(aflow: Flow) -> Flow:
    """
    Build the optimized employee appraisal workflow with parallel processing.
    
    Workflow Steps:
    1. User uploads employee data file (Excel or CSV)
    2. Read and parse employee data
    3. Process each employee's appraisal in PARALLEL
    4. Flatten results (single transformation)
    5. Generate Excel file for download
    6. Provide download button to user
    7. Return summary to agent
    """
    
    # ========================================================================
    # STEP 1: USER ACTIVITY - FILE UPLOAD
    # ========================================================================
    user_flow = aflow.userflow(name="file_upload_flow")
    
    file_upload_node = user_flow.field(
        direction="input",
        name="employee_data_file",
        display_name="Employee Data File",
        kind=UserFieldKind.File,
        description="Upload the employee data file (Excel .xlsx or CSV .csv)",
        text="Please upload your employee data file (Excel or CSV format)"
    )
    
    # Define edges within the userflow
    user_flow.edge(START, file_upload_node)
    user_flow.edge(file_upload_node, END)
    
    # ========================================================================
    # STEP 2: READ EMPLOYEE DATA
    # ========================================================================
    read_data_node = aflow.tool("read_employee_data")
    
    # Map the uploaded file path to the tool input
    read_data_node.map_input(
        input_variable="file_path",
        expression='flow["file_upload_flow"]["employee_data_file"].output.value'
    )
    
    # ========================================================================
    # STEP 3: PARALLEL FOREACH - CALCULATE APPRAISAL FOR EACH EMPLOYEE
    # ========================================================================
    # Create a foreach loop that processes each employee in PARALLEL
    # WITHOUT output_schema - let it automatically collect tool outputs
    foreach_flow = aflow.foreach(
        item_schema=EmployeeData
    ).policy(kind=ForeachPolicy.PARALLEL)  # EXPLICIT PARALLEL PROCESSING
    
    # Map the read_data_node output to the foreach input
    foreach_flow.map_input(
        input_variable="items",
        expression='flow["read_employee_data"].output'
    )
    
    # Inside the foreach, call the appraisal calculation tool
    calculate_node = foreach_flow.tool("calculate_employee_appraisal")
    
    # Map the current employee item to the tool input
    calculate_node.map_input(
        input_variable="employee",
        expression="parent._current_item"
    )
    
    # Define the foreach flow sequence
    foreach_flow.sequence(START, calculate_node, END)
    
    # ========================================================================
    # STEP 4: GENERATE EXCEL FILE WITH RESULTS
    # ========================================================================
    generate_excel_node = aflow.tool("generate_appraisal_excel")
    
    # Map foreach output directly - it's already clean AppraisalResult objects
    generate_excel_node.map_input(
        input_variable="results",
        expression='[item[0].get("data", item[0]) if isinstance(item, list) and len(item) > 0 and isinstance(item[0], dict) else item.get("data", item) if isinstance(item, dict) else item for item in flow["foreach_1"].output]'
    )
    
    # ========================================================================
    # STEP 5: MAP WORKFLOW OUTPUT
    # ========================================================================
    # Use the same flattening expression for consistency
    aflow.map_output(
        output_variable="results",
        expression='[item[0].get("data", item[0]) if isinstance(item, list) and len(item) > 0 and isinstance(item[0], dict) else item.get("data", item) if isinstance(item, dict) else item for item in flow["foreach_1"].output]'
    )
    aflow.map_output(
        output_variable="total_employees_processed",
        expression='len(flow["foreach_1"].output)'
    )
    aflow.map_output(
        output_variable="message",
        expression='"Successfully processed " + str(len(flow["foreach_1"].output)) + " employees. Download the complete results using the link provided."'
    )
    aflow.map_output(
        output_variable="download_file",
        expression='flow["generate_appraisal_excel"].output'
    )
    
    # ========================================================================
    # STEP 6: BUILD WORKFLOW SEQUENCE
    # ========================================================================
    aflow.edge(START, user_flow)
    aflow.edge(user_flow, read_data_node)
    aflow.edge(read_data_node, foreach_flow)
    aflow.edge(foreach_flow, generate_excel_node)
    aflow.edge(generate_excel_node, END)
    
    return aflow

# Made with Bob
