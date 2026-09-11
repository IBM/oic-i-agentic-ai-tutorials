from ibm_watsonx_orchestrate.agent_builder.tools import tool
from ibm_watsonx_orchestrate.agent_builder.tools.types import (
    PythonToolKind,
    PluginContext,
    AgentPreInvokePayload,
    AgentPreInvokeResult,
    AgentPreInvokeType,
    TextContent,
    Message
)
@tool(
    description="RBAC plugin for salary sub-agent access control",
    kind=PythonToolKind.AGENTPREINVOKE
)
def rbac_plugin(
    plugin_context: PluginContext,
    agent_pre_invoke_payload: AgentPreInvokePayload
) -> AgentPreInvokeResult:

    result = AgentPreInvokeResult(modified_payload=agent_pre_invoke_payload)
    action = plugin_context.metadata.get("action")

    # Safely read state → context → user_profile
    state = plugin_context.state or {}
    context = state.get("context", {})
    user_profile = context.get("user_profile", {})

    # Read is_manager_1 flag (default False)
    is_manager = bool(user_profile.get("is_manager", False))


    result.continue_processing = is_manager



    return result
