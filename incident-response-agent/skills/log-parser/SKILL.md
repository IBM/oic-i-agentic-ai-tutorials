---
name: log-parser
description: >
  Reads raw error logs and an alert message to figure out what broke and why.
  Use this skill first whenever an engineer pastes logs or says "something broke",
  "we have an incident", "error rate spiked", or "here are the logs".
  Run this BEFORE incident-brief-summarizer. Outputs a short diagnosis.
---

# Log Parser

Read the logs. Find the error. Check if a deploy caused it. Output a clear diagnosis.

---

## Step 1 — Find the Error

Look through the logs for:
- Any line with ERROR, FATAL, Exception, or a 5xx status code
- The first time the error appeared
- How often it's repeating (once? every few seconds?)
- Which service or file it's coming from

---

## Step 2 — Check the Deploy

Look at the timestamps:
- When did the first error appear?
- Was there a deploy in the 30 minutes before that?
- If yes → the deploy is the likely cause

See `references/common-errors.md` for what specific errors usually mean.

---

## Step 3 — Output the Diagnosis

Write a short diagnosis in this format:

```
## Diagnosis

**What broke:** [one sentence — e.g., "payment-service is returning 500 errors"]
**First error at:** [timestamp]
**Error type:** [e.g., NullPointerException / DB connection refused / OOMKilled]
**Likely cause:** [e.g., "deploy at 03:01 introduced an unhandled null check"]
**Confidence:** [High / Medium / Low]
**Affected users:** [e.g., "~30% of checkout requests failing"]

**Top 3 actions:**
1. [e.g., Roll back the 03:01 deploy to payment-service]
2. [e.g., Check DB connection pool — connections may be exhausted]
3. [e.g., Page the payment-service owner if rollback doesn't help]
```

---

## Guidelines

- Keep it short — the engineer is half asleep
- If you're not sure, say so — "Confidence: Low" is better than a wrong answer
- Don't suggest actions that could make things worse without flagging the risk
- Pass the diagnosis directly to incident-brief-summarizer

## References
- `references/common-errors.md`