# Harness Engineering — tutorial prompt files

Prompt files for the IBM Developer tutorial **Build reliable agent tools with OpenAPI tool contracts**.

Each file is one prompt you send to IBM Bob. Send them in the order below, one step at a
time, and wait for Bob to finish before sending the next. Point Bob at a file rather than
pasting it:

```
Implement the spec @create_project_and_rules_file.md
```

## Files used by the tutorial

| File | Tutorial step | What it does |
|---|---|---|
| `AGENTS.md` | Step 2 | The project contract: environment, pinned names and seed data, and the rules Bob follows in every later step. You paste this into the first prompt rather than sending it on its own. |
| `create_project_and_rules_file.md` | Step 2 | Creates the project folders and writes `AGENTS.md` to disk, then reads it back so you can confirm it is exact. |
| `build_mock_backend.md` | Step 3 | Builds the mock banking API: five seeded accounts, the business rules, the two endpoints, and request logging before validation. |
| `write_spec_a_anti_pattern.md` | Step 4 | Writes the permissive OpenAPI tool contract — four free-text parameters and a vague description. Deliberately weak. |
| `write_spec_b_mistake_proofed.md` | Step 5 | Writes the constrained tool contract — two parameters, one restricted to a list of valid accounts and one bounded by an amount range, with routing guidance in the description. |
| `add_servers_block_tunnel_url.md` | Step 6 | Adds a `servers` block with your tunnel URL to both specs, so Orchestrate can reach the API on your laptop. **Fill in your tunnel URL before sending.** |
| `deploy_both_agents.md` | Step 7 | Imports both specs as tools and creates the two agents, identical apart from the tool each one has. **Fill in your model ID before sending.** |
| `smoke_tests_hello_and_transfer.md` | Step 7 | Sends a greeting and one transfer request to each agent, and shows the arguments each one sent, from the trace and from the call log. |
| `test_both_contracts.md` | Step 8 | Runs the same four scenarios against both agents and quotes the arguments from `logs/calls.jsonl`. |
| `verify_acceptance_criteria.md` | Step 9 | Checks the project against the acceptance criteria in `AGENTS.md`, with evidence gathered at the time of checking. |

### Prompts that need a value from you

Two files contain a placeholder you replace before sending:

- `add_servers_block_tunnel_url.md` — the public tunnel URL from ngrok or cloudflared (Step 6).
- `deploy_both_agents.md` — the model ID from `orchestrate models list` (Step 7). Copy it exactly; a retyped ID that is one character out will make both agents fail on every message.

## Files not used by the current tutorial

An earlier draft built and validated an evaluation harness. That section was removed to keep
the tutorial focused, so these files are not referenced by any step. They are kept for
reference and may be used in a follow-up article:

- `create_golden_set.md`
- `build_evaluation_harness.md`
- `fallback_bob_drives_conversations.md`
- `run_full_evaluation.md`
- `show_borderline_grading_rows.md`
- `apply_author_verdicts.md`
- `write_results_report.md`

## Before you start

Clone this repository inside the project folder you open in Bob, so that `@filename`
references resolve from Bob's working directory.
