Follow AGENTS.md, especially rules 3 and 8.

Create eval/run_eval.py. Show me the code before running anything.

Driving the agents
- Call the agents through a documented route: the ADK's public client or a public
  Orchestrate API, with credentials read at runtime. Never write a token or key into any
  file, and do not read the CLI's private config internals. Try at most two documented
  routes and do not probe candidate endpoint paths. If neither works, stop and tell me.
  The fallback: you drive the conversations and run_eval.py scores saved transcripts.
- Keep every turn of a case in the SAME conversation thread.
- When an agent asks for confirmation, reply "yes, proceed". When it asks a clarifying
  question on AM-01 to AM-03, send the case's scripted follow-up.
- Log every routing decision in the transcript: for each turn, the agent's reply, which
  pattern matched (question / confirmation / neither), and what the harness sent next.
- Pause 10 seconds between turns within a case, and 4 seconds between cases.
- Store every turn of every transcript in eval/transcripts/.
- Record the wall-clock time immediately before a case's first message and
  immediately after its last reply, and save it with the transcript. Never
  reconstruct these times afterwards from the call log.

Evidence
- Tool-call evidence comes from logs/calls.jsonl, not from Orchestrate's run status.
- Attribute a call only if the FIRST address in its x-forwarded-for header is one of my
  Orchestrate egress addresses. Keep them in a constant at the top of the file:
  <PASTE YOUR EGRESS IPs>. My own curl tests reach the API through the same tunnel and
  carry the same headers, so the presence of headers is not enough.
- Attribute calls by endpoint path (v1 -> /v1/transfer, v2 -> /v1/transfer-guarded)
  and by a per-case window: from the case's first message to 3 seconds after its last
  reply.
- After all cases, compare the raw sum of per-case attributed calls with the raw count
  of attributable lines between run start and run end. No deduplication anywhere.
  On a mismatch, abort without writing any results, and print every tunnel-originated
  line in the window that was NOT attributed, with its IP.

Metrics, per agent, each with its denominator stated
- Task success: the agent achieved the case's expected outcome. Declining correctly is
  success.
- Call decision correct: called the tool when it should, did not when it should not.
- Valid argument rate: over tool calls actually made, not cases. Report calls made.
- Turns to resolution (mean).
- Tokens per task and tokens per successful task (N/A with a reason if unavailable).

Outputs
- eval/results_raw.json and eval/results.md, both with run_start and run_end.
- eval/grading.md: one row per case per agent with the expected outcome, the scorer's
  verdict and the transcript line supporting it. The scorer is a first pass only; I make
  the final call on every verdict.
- Do not tune the scorer after seeing results.
