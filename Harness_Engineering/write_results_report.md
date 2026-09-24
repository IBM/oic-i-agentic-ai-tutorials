Follow AGENTS.md, especially rule 3.

Create RESULTS.md from eval/results_raw.json, eval/grading.md (author verdicts),
logs/calls.jsonl and the spec files. Quote every figure and every schema detail from
those files. Do not restate anything from memory.

1. Run metadata: run_start, run_end, model ID, attribution check result.
2. Summary table: task success (author verdicts) first, then the other metrics, each
   with its denominator.
3. Walkthroughs of case 3 (AM-01), case 4 (AM-02) and case 5 (AM-03), with the literal
   arguments quoted from logs/calls.jsonl.
4. A reconciliation table: calls per agent per case, with the per-case numbers written
   out beside every total. The grand total must equal the attribution check count.
5. "Where v2 still fails": every case v2 failed or handled awkwardly, with no spin.
   Label any evidence from outside the main run with its timestamp.
6. A parameter comparison, quoted from specs/transfer-v1.yaml and specs/transfer-v2.yaml.
7. Limitations: one run per case; single domain; single model; mock backend; any
   solo-rerun variance; the scorer was a first pass and task success uses author
   verdicts.

Write it plainly. Do not oversell the result.
