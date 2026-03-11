from ibm_watsonx_orchestrate.agent_builder.tools import tool
from ibm_watsonx_orchestrate.run.context import AgentRun

@tool
def update_user_context(
    context: AgentRun,
    user_age: int,
    user_login: str,
    user_password: str
) -> dict:
    """
    Updates the user context with the provided user information.

    Args:
        context (AgentRun): The agent run context.
        user_age (int): The age of the user.
        user_login (str): The login of the user.
        user_password (str): The password of the user.

    Returns:
        dict: The updated context dictionary.
    """
    req_context = context.request_context
    
    # Check if request_context is None
    if req_context is None:
        return {
            "error": "Request context is not available",
            "message": "Failed to update context"
        }

    # Bulk update
    req_context.update({
        "user_age": user_age,
        "user_login": user_login,
        "user_password": user_password,
    })
    age = req_context.get("user_age")
    login = req_context.get("user_login")
    password = req_context.get("user_password")
    
    return {
        "message": "Context updated successfully",
        "user_age": age,
        "user_login": login,
        "user_password": password
    }





@tool
def fetch_user_context(context: AgentRun) -> dict:
    """
    Fetches and returns the user context.

    Args:
        context (AgentRun): The agent run context.

    Returns:
        dict: The user information from context.
    """
    req_context = context.request_context
    
    # Check if request_context is None
    if req_context is None:
        return {
            "error": "Request context is not available",
            "message": "No context data"
        }
    
    # Try to get keys without triggering full context merge
    try:
        # Access only keys you care about
        user_keys = ["user_age", "user_login", "user_password"]
        result = {k: req_context.get(k) for k in user_keys if k in req_context}
        return result if result else {"message": "No user data in context"}
    except Exception as e:
        return {"error": f"Failed to fetch context: {str(e)}"}