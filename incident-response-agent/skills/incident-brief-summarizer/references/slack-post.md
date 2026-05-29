# Slack Post Template

Use this template to write incident updates for Slack.

---

## Template (Blank)

```
[severity emoji] [One sentence: what's broken]

**Started:** [timestamp]
**Impact:** [who/what is affected + percentage/scale]
**Status:** [Investigating / Identified / Fixing / Monitoring]

**What we know:**
- [Key fact 1]
- [Key fact 2]
- [Key fact 3 — keep it to 3-4 bullets max]

**Next steps:**
- [Action 1]
- [Action 2]

**Owned by:** [your-name]
**Next update:** [time — usually 15-30 min]
```

---

## Severity Emoji Guide

- 🔴 **P1 (Critical)** — Service down, major user impact, revenue loss
- 🟠 **P2 (High)** — Degraded service, some users affected, workaround exists
- 🟡 **P3 (Medium)** — Minor issue, few users affected, low urgency

---

## Example (Filled)

**Scenario:** Payment service returning 500 errors after 03:01 deploy

```
🔴 Payment service is returning 500 errors — checkouts are failing

**Started:** 2024-01-15 03:04 UTC
**Impact:** ~30% of checkout requests failing (est. 200 users affected)
**Status:** Identified — rolling back deploy

**What we know:**
- First error at 03:04, 3 minutes after payment-service deploy
- NullPointerException in new discount calculation code
- Error rate: 30% of requests (intermittent, not all users)

**Next steps:**
- Rolling back payment-service to v2.4.1 (ETA: 5 min)
- Monitoring error rate after rollback

**Owned by:** [your-name]
**Next update:** 03:20 UTC (15 min)
```

---

## Writing Tips

1. **First line = headline** — engineer should know what's broken without reading further
2. **Impact in numbers** — "30% of requests" is better than "some users"
3. **Status = action verb** — "Investigating" / "Rolling back" / "Monitoring"
4. **Keep bullets short** — one line each, no nested lists
5. **Confidence matters** — if you're not sure, say "investigating" not "root cause is X"
6. **Calm tone** — even for P1, panic doesn't help
7. **Next update time** — always include, usually 15-30 min

---

## Common Mistakes to Avoid

❌ **Too technical:** "NullPointerException in DiscountCalculator.java line 47"
✅ **Plain English:** "Error in new discount calculation code"

❌ **Too vague:** "Something is broken"
✅ **Specific:** "Payment service returning 500 errors"

❌ **Too long:** 20+ lines of details
✅ **Concise:** Under 15 lines, key facts only

❌ **Uncertain language:** "We think maybe it's the deploy?"
✅ **Clear confidence:** "Likely caused by 03:01 deploy (high confidence)"