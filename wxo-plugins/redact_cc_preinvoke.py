# pre_invoke_redact_cc.py
import re
from typing import List, Dict, Any

from ibm_watsonx_orchestrate.agent_builder.tools import tool
from ibm_watsonx_orchestrate.agent_builder.tools.types import (
    PythonToolKind,
    PluginContext,
    AgentPreInvokePayload,
    AgentPreInvokeResult,
    TextContent,
    Message,
)


@tool(
    description="Redacts credit card numbers in user messages before tool invocation",
    kind=PythonToolKind.AGENTPREINVOKE
)
def redact_credit_card_preinvoke_plugin(
    plugin_context: PluginContext,
    agent_pre_invoke_payload: AgentPreInvokePayload,
) -> AgentPreInvokeResult:
    """
    Pre-invoke plugin that scans incoming user messages for credit card numbers
    and replaces them with a masked representation before the tool is called.
    
    This ensures that tools never receive full credit card numbers, only redacted versions.
    
    Supported formats (very common patterns):
        • 1234 5678 9012 3456
        • 1234-5678-9012-3456
        • 1234567890123456
        • 1234 567890 12345
        • 5-digit/4-digit groupings, etc.
    
    The masking keeps the last four digits visible (e.g. **** **** **** 1234).
    
    Args:
        plugin_context (PluginContext): Information about the request.
        agent_pre_invoke_payload (AgentPreInvokePayload): The payload containing the
            messages before tool invocation.
    
    Returns:
        AgentPreInvokeResult: Result indicating whether processing should continue
            and, if so, the possibly-modified payload.
    """
    result = AgentPreInvokeResult()
    
    # If there are no messages, nothing to do.
    if (
        not agent_pre_invoke_payload
        or not agent_pre_invoke_payload.messages
    ):
        result.continue_processing = True
        result.modified_payload = agent_pre_invoke_payload
        return result

    # Regular expression that matches typical credit card number formats.
    # It looks for 13-19 consecutive digits optionally separated by spaces, hyphens, or other whitespace.
    cc_regex = re.compile(
        r"""(?<!\d)               # no digit before
            (?:\d[\s-]?){13,19}   # 13-19 digits, optional whitespace or hyphen between each
            (?!\d)                # no digit after
        """,
        re.VERBOSE,
    )

    def mask_match(match: re.Match) -> str:
        """Replace all but the last four digits with asterisks while preserving separators."""
        raw = match.group(0)
        # Remove all whitespace and hyphens to count digits
        digits = re.sub(r"[\s-]", "", raw)
        if len(digits) < 4:
            return raw  # shouldn't happen, but safe-guard

        # Keep the last 4 digits
        visible = digits[-4:]
        # Build masked part, preserving original separator positions
        masked = []
        digit_index = 0
        for ch in raw:
            if ch.isdigit():
                if len(digits) - digit_index > 4:
                    masked.append("*")
                else:
                    masked.append(visible[digit_index - (len(digits) - 4)])
                digit_index += 1
            else:
                # preserve all whitespace characters and hyphens
                masked.append(ch)
        return "".join(masked)

    # Process each message - redact credit card numbers in user messages
    modified_messages: List[Message] = []
    for msg in agent_pre_invoke_payload.messages:
        # Only text content can be redacted; other content types are passed through.
        if hasattr(msg, "content") and isinstance(msg.content, TextContent):
            original_text = msg.content.text or ""
            redacted_text = cc_regex.sub(mask_match, original_text)

            # Build a new TextContent and Message with the redacted text
            new_content = TextContent(type="text", text=redacted_text)
            new_msg = Message(role=msg.role, content=new_content)
        else:
            # Non-text messages are left unchanged
            new_msg = msg

        modified_messages.append(new_msg)

    # Create a copy of the original payload with the modified messages
    modified_payload = agent_pre_invoke_payload.copy(deep=True)
    modified_payload.messages = modified_messages

    result.continue_processing = True
    result.modified_payload = modified_payload
    
    return result

# orchestrate tools import -k python -f redact_cc_preinvoke.py

# Made with Bob
