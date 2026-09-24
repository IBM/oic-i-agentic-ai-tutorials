Follow AGENTS.md, especially rules 2, 4, 8 and 9.

Deploy the experiment to my watsonx Orchestrate instance, in this order:

1. Import specs/transfer-v1.yaml and specs/transfer-v2.yaml as OpenAPI tools.
2. List the tools in Orchestrate and confirm exactly one transferFunds and one
   transferToOwnAccount exist.
3. Create two agents:
     transfer_agent_v1 — tool: transferFunds
     transfer_agent_v2 — tool: transferToOwnAccount
   Both get the pinned description and the pinned instruction block from AGENTS.md,
   verbatim, and this model ID for both: <PASTE THE EXACT ID FROM orchestrate models list>

Before you create anything, print the exact calls or commands you intend to run and
wait for my confirmation.

After both agents exist:
- read back each agent's model, description, instructions and tools as a table
- fetch each agent's instruction block from Orchestrate separately and print a SHA-256
  hash of each; do not hash one string and apply it to both
Then stop.
