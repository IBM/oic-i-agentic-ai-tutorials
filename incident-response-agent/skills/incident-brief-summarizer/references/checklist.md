# Action Checklist Template

Use this template to create a step-by-step action plan for the engineer.

---

## Template (Blank)

```
## Immediate Actions
- [ ] [Action 1 with imperative verb]
      Why: [one line explanation]
- [ ] [Action 2]
      Why: [one line explanation]

## If That Doesn't Work
- [ ] [Escalation action 1]
      Why: [one line explanation]
- [ ] [Escalation action 2]
      Why: [one line explanation]

## After Resolution
- [ ] Post update to Slack in 15 minutes
- [ ] Open a post-mortem ticket once resolved
```

---

## Example (Filled)

**Scenario:** Payment service returning 500 errors after 03:01 deploy

```
## Immediate Actions
- [ ] Rollback payment-service to v2.4.1
      Why: Error started 3 min after deploy, high confidence it's the cause

- [ ] Monitor error rate for 5 minutes after rollback
      Why: Confirm rollback fixed the issue before closing incident

- [ ] Check if any payments are stuck in "pending" state
      Why: Failed requests may have left incomplete transactions

## If That Doesn't Work
- [ ] Check database connection pool status
      Why: 500 errors can also be caused by exhausted DB connections

- [ ] Page payment-service owner (@jane-doe)
      Why: If rollback didn't help, need domain expert to investigate

- [ ] Enable debug logging on payment-service
      Why: Get more detailed error info for root cause analysis

## After Resolution
- [ ] Post update to Slack in 15 minutes
- [ ] Open a post-mortem ticket once resolved
```

---

## Writing Tips

1. **Use imperative verbs** — "Rollback", "Check", "Page", "Enable"
2. **One action per checkbox** — don't combine multiple steps
3. **Add "Why" for each action** — helps engineer understand priority
4. **Order by priority** — most important actions first
5. **Include escalation path** — what to do if first actions don't work
6. **Always end with follow-up** — Slack update + post-mortem

---

## Action Categories

### Immediate Actions
- Things to do right now (0-5 minutes)
- Usually: rollback, check status, verify impact
- High confidence actions based on diagnosis

### If That Doesn't Work
- Escalation steps (5-30 minutes)
- Usually: page owner, enable debugging, check infrastructure
- Lower confidence actions or deeper investigation

### After Resolution
- Follow-up tasks (after incident is resolved)
- Always include: Slack update, post-mortem ticket
- Don't forget these — they're important for learning

---

## Common Action Patterns

### For Deploy-Related Issues
```
- [ ] Rollback [service] to [previous version]
      Why: Error started immediately after deploy
- [ ] Verify rollback completed successfully
      Why: Ensure new version is actually running
- [ ] Monitor error rate for 5 minutes
      Why: Confirm issue is resolved
```

### For Database Issues
```
- [ ] Check database connection pool status
      Why: Connection exhaustion causes 500 errors
- [ ] Review slow query logs
      Why: Identify queries causing timeouts
- [ ] Check database CPU/memory usage
      Why: Resource exhaustion can cause failures
```

### For Infrastructure Issues
```
- [ ] Check pod/container status in Kubernetes
      Why: Verify service is actually running
- [ ] Review resource limits (CPU/memory)
      Why: OOMKilled indicates memory limit too low
- [ ] Check network policies
      Why: Connection refused may be firewall/policy issue
```

### For Unknown Issues
```
- [ ] Enable debug logging on [service]
      Why: Get more detailed error information
- [ ] Page [service] owner
      Why: Need domain expert to investigate
- [ ] Check recent changes (deploys, config, infrastructure)
      Why: Identify what changed before error started
```

---

## Example: Complete Checklist for Different Scenarios

### Scenario 1: NullPointerException after deploy
```
## Immediate Actions
- [ ] Rollback payment-service to v2.4.1
      Why: NPE in new code, high confidence deploy is cause
- [ ] Monitor error rate after rollback
      Why: Verify issue is resolved

## If That Doesn't Work
- [ ] Check if error is in different code path
      Why: May be unrelated to deploy
- [ ] Page payment-service owner
      Why: Need code review of recent changes

## After Resolution
- [ ] Post update to Slack in 15 minutes
- [ ] Open a post-mortem ticket once resolved
```

### Scenario 2: Database connection refused
```
## Immediate Actions
- [ ] Check database status (is it running?)
      Why: Connection refused = can't reach database
- [ ] Verify connection string in service config
      Why: Wrong hostname/port causes connection refused
- [ ] Check network policies between service and DB
      Why: Firewall may be blocking connection

## If That Doesn't Work
- [ ] Restart database connection pool
      Why: Pool may be in bad state
- [ ] Page database team
      Why: May be database-side issue
- [ ] Check if other services can connect to DB
      Why: Isolate if it's service-specific or DB-wide

## After Resolution
- [ ] Post update to Slack in 15 minutes
- [ ] Open a post-mortem ticket once resolved
```

### Scenario 3: OOMKilled (out of memory)
```
## Immediate Actions
- [ ] Rollback to previous version
      Why: New code may have memory leak
- [ ] Check memory usage trends before crash
      Why: Identify if it's gradual leak or sudden spike
- [ ] Verify memory limits are appropriate
      Why: Limit may be too low for workload

## If That Doesn't Work
- [ ] Increase memory limit temporarily
      Why: Buy time to investigate root cause
- [ ] Enable memory profiling
      Why: Identify what's consuming memory
- [ ] Page service owner for code review
      Why: May need to optimize memory usage

## After Resolution
- [ ] Post update to Slack in 15 minutes
- [ ] Open a post-mortem ticket once resolved