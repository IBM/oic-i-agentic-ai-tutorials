Follow AGENTS.md.

Verify the global acceptance criteria in AGENTS.md one by one. For each, state PASS or
FAIL and the evidence you checked NOW — a file path, a command output, a hash. Do not
mark anything PASS because you believe you did it earlier.

- Run the smoke tests in mock_api/README.md and quote their output.
- Fetch both instruction blocks from Orchestrate separately and hash each.
- Count the tunnel-originated calls.jsonl lines for the final run only, and reconcile
  them with the attribution check.

Then list, in one line each, anything in this project that a reader reproducing it
would be likely to get differently, and why.
