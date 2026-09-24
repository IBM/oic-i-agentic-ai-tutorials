Fall back to the route in the harness spec: you drive the conversations, and
run_eval.py only scores saved transcripts.

- Use the same MCP chat tool you used for the Step 6 smoke tests.
- Each case in one thread, in golden_set order, v1 then v2.
- Send the scripted follow-up when the agent asks a clarifying question, and
  "yes, proceed" when it asks for confirmation.
- 10 seconds between turns, 4 seconds between cases.
- Record the wall-clock time immediately before each case's first message and
  immediately after its last reply, and save it with the transcript. Take these at
  the moment each conversation runs — never reconstruct them from the call log.
- Save every turn and every routing decision to eval/transcripts/.

run_eval.py then reads those transcripts plus logs/calls.jsonl and scores them, with
the attribution check and metrics exactly as specified. It makes no calls to
Orchestrate.
