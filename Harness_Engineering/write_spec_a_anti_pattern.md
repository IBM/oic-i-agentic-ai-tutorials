Follow AGENTS.md.

Create specs/transfer-v1.yaml — an OpenAPI 3.0 spec over POST /v1/transfer.
Include the openapi: 3.0.3 declaration and an info block. Do not add a servers block
yet; that comes in Step 5.

This spec must exhibit common anti-patterns DELIBERATELY. Do not improve it, do not add
constraints, do not add guidance. Its weakness is the experiment.

  operationId: transferFunds
  summary:     "Transfers funds between accounts."   <- exactly this, vague
  description: "Transfers funds between accounts."   <- same text; Orchestrate requires it
  Request body properties, ALL optional, NO constraints:
    from_account: string
    to_account:   string
    amount:       number
    currency:     string
  Response schema: return the full account object with every field.

After writing it, list in one line each anti-pattern present and why a model would
plausibly get it wrong. Then stop.
