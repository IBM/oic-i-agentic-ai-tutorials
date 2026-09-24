Two smoke tests, then stop:

1. Send "Hello" to transfer_agent_v1 and to transfer_agent_v2. Report each response.
2. Send "Transfer 200 to my savings" to each agent. When it asks for confirmation,
   reply "yes, proceed" in the same conversation. For each agent, show me the final
   response and the tool-call arguments — from the Orchestrate trace if available, and
   the matching lines from logs/calls.jsonl.

If you cannot retrieve tool-call arguments from either source, stop and tell me.
