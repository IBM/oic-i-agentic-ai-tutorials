# AGENTS.md — Poka-yoke tool contract demo

## What this project is
A controlled experiment for a published tutorial. Two watsonx Orchestrate agents are
built with identical instructions and different tool contracts, to demonstrate that
mistake-proofing a tool schema improves agent reliability without prompt changes.

Reproducibility matters more than creativity. Another person running the same prompts
must get a materially identical result.

## Environment
- Python 3.11, FastAPI, uvicorn — use the project venv (source venv/bin/activate)
- Mock API on port 8080
- Domain: Australian retail banking, AUD
- Run: uvicorn mock_api.main:app --port 8080
- Smoke tests: see mock_api/README.md
- watsonx Orchestrate reaches the mock API through a public tunnel URL that the user
  supplies. You cannot start long-running processes (the server, the tunnel): ask the
  user to run them.

## THE CONTROLLED VARIABLE — NON-NEGOTIABLE
The two agents MUST share the same model, the same description, the same instruction
block character for character, and the same mock backend.

They MUST differ ONLY in the OpenAPI specification imported as their toolset.

Never modify Spec A to make agent v1 perform better.
Never add tools, few-shot examples, guardrail text or instruction changes to agent v2.
The spec is the only lever. If you are tempted to change anything else to improve a
result: STOP and tell me. Do not do it.

## Pinned strings — reproduce exactly, never paraphrase

Agent description (both agents):
"Helps a retail banking customer move money between their own accounts."

Agent instruction block (both agents):
"You are a retail banking assistant for Alex Chen. Help the customer transfer money
between their own accounts. Confirm the destination and the amount before you execute
a transfer. Be concise."

Agent names: transfer_agent_v1, transfer_agent_v2
(Orchestrate agent names allow letters, digits and underscores only.)

## Model
Both agents use the same model: the exact model ID the user supplies, copied from
`orchestrate models list`. Never infer a model from other agents and never retype an ID.

## Spec requirements
Every OpenAPI spec in specs/ must include an openapi: 3.0.3 declaration, an info block,
a servers block with the tunnel URL (added in Step 5), and a description on every
operation. summary and description carry identical text.

## Pinned seed state
Signed-in user: U-1001, Alex Chen
- EVERYDAY      ACC-100   4820.50 AUD   active   (source account)
- SAVINGS       ACC-200  15300.00 AUD   active
- OFFSET        ACC-300   2100.00 AUD   active
- TERM_DEPOSIT  ACC-400  50000.00 AUD   locked until 2026-11-02
- OLD_SAVER     ACC-500      0.00 AUD   closed

## Rules of engagement
1. Work one step at a time. Summarise what you created and stop. Wait for my go-ahead.
2. Before creating anything in watsonx Orchestrate, print the exact calls or commands
   you intend to run and pause for confirmation.
3. Never fabricate a metric. If a number is not retrievable, write N/A and say why.
4. If an Orchestrate affordance does not behave as expected, stop and report exactly
   what you tried and what came back. Do not work around it silently. Do not guess at
   endpoint shapes.
5. Show your first-pass draft before any hardening pass, so the delta is visible.
6. Log every request to the mock API — including requests the API rejects — to
   logs/calls.jsonl with timestamp, path, raw body, response status and forwarding
   headers.
7. Prefer the simplest implementation that satisfies the step. Tell me what you chose
   wherever this file does not specify something.
8. Never infer or substitute a value that was not given to you. If something is
   missing, stop and ask.
9. After any timed-out write to watsonx Orchestrate, list the current state before
   retrying. Never create a duplicate tool or agent.

## Global acceptance criteria
- Mock API runs; the smoke tests in mock_api/README.md pass when run now, output quoted
- Both agents live in Orchestrate and answer in the chat panel
- Both agents use the same model ID
- Instruction blocks, fetched from Orchestrate separately for each agent, hash identically
- eval/results.md, eval/grading.md and RESULTS.md populated from real runs, not estimates
- logs/calls.jsonl contains the raw arguments for every call both agents made, and the
  calls attributed by the harness equal the tunnel-originated lines for the run
