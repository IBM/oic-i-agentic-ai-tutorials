import re
from ibm_watsonx_orchestrate.agent_builder.tools import tool
from ibm_watsonx_orchestrate.agent_builder.tools.types import PythonToolKind, PluginContext, AgentPreInvokePayload, AgentPreInvokeResult


@tool(
    description="Pre-invoke plugin that redacts credit card numbers in user input before the agent processes it.",
    kind=PythonToolKind.AGENTPREINVOKE
)
def guardrail_cc_preinvoke(plugin_context: PluginContext, agent_pre_invoke_payload: AgentPreInvokePayload) -> AgentPreInvokeResult:
    """
    Redacts credit card numbers in user messages.
    Changes: 1234 5678 9012 3456
    To:      **** **** **** 3456
    """
    
    user_input = ''
    modified_payload = agent_pre_invoke_payload
    res = AgentPreInvokeResult()
    
    if agent_pre_invoke_payload and agent_pre_invoke_payload.messages:
        user_input = agent_pre_invoke_payload.messages[-1].content.text
    
    def redact_credit_cards(text: str) -> str:
        """
        Redacts credit card numbers, keeping only the last 4 digits visible.
        
        Args:
            text (str): The input text containing potential credit card numbers.
        
        Returns:
            str: The text with credit card numbers redacted.
        """
        # Pattern: 4 groups of 4 digits separated by spaces
        # Example: 1234 5678 9012 3456
        pattern = r'(\d{4}) (\d{4}) (\d{4}) (\d{4})'
        
        # Replace with asterisks, keeping last 4 digits
        # \4 refers to the 4th capture group (last 4 digits)
        redacted = re.sub(pattern, r'**** **** **** \4', text)
        
        return redacted
    
    # Redact credit cards in the user input
    modified_text = redact_credit_cards(user_input)
    
    # Update the payload with redacted text
    modified_payload.messages[-1].content.text = modified_text
    res.modified_payload = modified_payload
    res.continue_processing = True
    
    return res

# Made with Bob
