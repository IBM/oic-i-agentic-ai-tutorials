---
name: incident-brief-summarizer
description: >
  Takes a diagnosis from log-parser and writes a Slack incident post and
  an action checklist. Use this skill second, after log-parser has run.
  Also triggers on: "write the Slack post", "I need an incident update",
  "write up what happened", "give me the status message".
  Output is copy-paste ready — the engineer should not need to edit it.
---

# Incident Brief Summarizer

Take the diagnosis and turn it into two things the engineer can use immediately:
a Slack post for the team, and a checklist of what to do next.

---

## Step 1 — Read the Diagnosis

From log-parser, pick out:
- What broke (plain English)
- When it started
- Likely cause + confidence level
- User impact
- Top actions

---

## Step 2 — Write the Slack Post

Use `references/slack-post.md` as the format.

Rules:
- First line: severity emoji + one sentence saying what's broken
- Keep it under 15 lines — people read this on their phone
- If confidence is Low, say "investigating" not "root cause is X"
- End with: who owns the incident + when the next update is

---

## Step 3 — Write the Action Checklist

Use `references/checklist.md` as the format.

For each action from the diagnosis:
- Write it as a checkbox with an imperative verb ("Rollback", "Check", "Page")
- Add one line explaining why

Always end the checklist with:
- [ ] Post update to Slack in 15 minutes
- [ ] Open a post-mortem ticket once resolved

---

## Step 4 — Output

Produce both documents separated clearly:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📢 SLACK POST  (copy → #incidents)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[slack post here]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ ACTION CHECKLIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[checklist here]
```

---

## Guidelines

- Copy-paste ready — no placeholders left unfilled except [your-name]
- Calm tone even for P1 — panic doesn't help anyone at 3 AM
- Don't repeat the same info twice across the two documents

## References
- `references/slack-post.md`
- `references/checklist.md`