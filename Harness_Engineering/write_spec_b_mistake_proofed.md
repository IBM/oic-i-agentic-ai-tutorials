Follow AGENTS.md, including rule 5.

First, write a first-pass OpenAPI 3.0 spec over POST /v1/transfer-guarded, without any
special hardening effort. Show it to me. Do not save it yet.

Then apply mistake-proofing in this order, stating which rule each change implements,
and save the result as specs/transfer-v2.yaml:

1. DELETE parameters the model must never supply:
   - from_account (resolved server-side from the session)
   - currency (fixed by the endpoint, folded into the field name)
2. CONSTRAIN what remains:
   - to_account: string, enum [SAVINGS, OFFSET, TERM_DEPOSIT], required,
     description: "The destination account. Must be one of the user's linked
     accounts. EVERYDAY is the implicit source and is not a valid destination."
   - amount_aud: number, minimum 1, maximum 10000, required
3. ROUTE in the description. operationId: transferToOwnAccount. Put this text in both
   summary and description, verbatim:
   "Transfer funds from the signed-in user's everyday account to one of their linked
   accounts. Use for user-initiated transfers between the user's own accounts. Do NOT
   use for third-party payments (use createPayeePayment) or for scheduled or recurring
   transfers (use scheduleTransfer)."
4. TRIM the response to only: status, destination, amount_aud, new_balance_aud.
5. DOCUMENT the 422 remediation response.

Include the openapi: 3.0.3 declaration and an info block. No servers block yet.
Finish with a parameter count: Spec A free parameters vs Spec B constrained parameters.
Then stop.
