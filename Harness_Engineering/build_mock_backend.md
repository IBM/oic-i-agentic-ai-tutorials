Follow AGENTS.md. Confirm the three non-negotiables back to me in one line first.

Build mock_api/main.py: a FastAPI app simulating a retail bank, using the pinned seed
state in AGENTS.md exactly.

Expose two endpoints over the SAME underlying state and SAME business logic:

  POST /v1/transfer — permissive surface
    Request fields, all optional: from_account, to_account, amount, currency
    Success response: the full account object with every field

  POST /v1/transfer-guarded — guarded surface
    Request fields, both required: to_account, amount_aud
    The source is always EVERYDAY (ACC-100), resolved server-side from the session.
    Success response: exactly status, destination, amount_aud, new_balance_aud

Accounts:
- One shared resolver for both endpoints: an account resolves by name (EVERYDAY,
  SAVINGS, OFFSET, TERM_DEPOSIT, OLD_SAVER) or ID (ACC-100 etc.), case-insensitive.
  Same rules on both endpoints.
- For the guarded endpoint, define the valid destinations once, as a Literal type alias
  ["SAVINGS", "OFFSET", "TERM_DEPOSIT"], and derive the list used in error messages
  from it with typing.get_args. Type to_account in the request model with that alias.
- Type amount_aud as a number with a minimum of 1 only. Do NOT cap it in the model.

Business rules for both endpoints: reject transfers from closed or locked accounts;
reject amounts <= 0; reject unknown accounts; reject amounts > 10000 as requiring
approval.

Error style — the endpoints differ ONLY here:
- /v1/transfer returns bare HTTP 400 {"error": "invalid request"} for EVERY failure,
  including request validation failures. Override FastAPI's default validation
  response for this path.
- /v1/transfer-guarded returns HTTP 422 with an instructive remediation message in an
  "error" field, naming only the field that failed and only valid values. Examples:
    "to_account must be one of SAVINGS, OFFSET, TERM_DEPOSIT."
    "Amounts above 10000 AUD require createPaymentApproval. Offer to start an approval."
  Never list EVERYDAY as a valid destination.

Logging: log every request to either endpoint in middleware, BEFORE validation, per
rule 6 — timestamp, path, raw body (if not valid JSON, the raw text), response status
and forwarding headers. Requests FastAPI rejects must still be logged.

Write mock_api/README.md with the run command and these smoke tests:
  POST /v1/transfer {"from_account":"ACC-100","to_account":"ACC-200","amount":100,
    "currency":"AUD"}
  POST /v1/transfer-guarded {"to_account":"SAVINGS","amount_aud":200}
    → 200 with destination
  POST /v1/transfer-guarded {"to_account":"SAVINGS","amount_aud":99999}
    → 422 pointing to createPaymentApproval

Then stop. Do not write any OpenAPI specs yet.
