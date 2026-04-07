from ibm_watsonx_orchestrate.agent_builder.tools import tool

@tool
def get_ssn_info() -> str:
    """Fetches personal user SSN"""
    return "User SSN is 123-45-6789"
