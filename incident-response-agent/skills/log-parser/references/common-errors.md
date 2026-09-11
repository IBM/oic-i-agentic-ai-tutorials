# Common Errors Reference

This document helps identify common error patterns and their likely causes.

---

## HTTP Errors

### 500 Internal Server Error
- **Meaning:** Unhandled exception in application code
- **Common causes:**
  - NullPointerException / AttributeError
  - Unhandled edge case in new code
  - Database query failure
  - Missing environment variable
- **Confidence:** High if error started after a deploy

### 502 Bad Gateway
- **Meaning:** Upstream service not responding or crashed
- **Common causes:**
  - Service crashed (OOMKilled, segfault)
  - Service not started after deploy
  - Load balancer can't reach service
  - Port mismatch in configuration
- **Confidence:** High if service logs show crash/restart

### 503 Service Unavailable
- **Meaning:** Service overloaded or temporarily down
- **Common causes:**
  - Too many requests (traffic spike)
  - All workers busy/blocked
  - Circuit breaker open
  - Intentional maintenance mode
- **Confidence:** Medium — check if traffic increased

### 504 Gateway Timeout
- **Meaning:** Upstream service took too long to respond
- **Common causes:**
  - Slow database query (missing index, lock contention)
  - External API call hanging
  - Infinite loop or deadlock
  - Resource exhaustion (CPU/memory)
- **Confidence:** High if response times increased

---

## Application/Runtime Errors

### NullPointerException / AttributeError / TypeError
- **Meaning:** Code tried to use a null/undefined/wrong-type value
- **Common causes:**
  - Missing null check in new code
  - API response format changed
  - Database returned unexpected null
  - Configuration value not set
- **Confidence:** High if error started after deploy
- **Action:** Roll back deploy, add null check

### OOMKilled (Out of Memory)
- **Meaning:** Container/process used too much memory and was killed
- **Common causes:**
  - Memory leak in new code
  - Large object held in memory (cache, list)
  - Recursive function without base case
  - Too many concurrent requests
- **Confidence:** High if memory usage was climbing
- **Action:** Roll back deploy, check memory profiling

### CrashLoopBackOff (Kubernetes)
- **Meaning:** Container keeps crashing on startup
- **Common causes:**
  - Missing environment variable
  - Can't connect to database/dependency
  - Port already in use
  - Syntax error in config file
- **Confidence:** High — check startup logs
- **Action:** Check pod logs, verify config

### Connection Refused / ECONNREFUSED
- **Meaning:** Can't connect to database/service
- **Common causes:**
  - Database is down
  - Wrong hostname/port in config
  - Network policy blocking connection
  - Connection pool exhausted
- **Confidence:** High if database is unreachable
- **Action:** Check database status, verify connection string

### Timeout / ETIMEDOUT
- **Meaning:** Operation took too long
- **Common causes:**
  - Slow query (missing index)
  - External API not responding
  - Network latency spike
  - Deadlock in database
- **Confidence:** Medium — check query performance
- **Action:** Check slow query logs, add timeout handling

---

## Deploy-Related Patterns

### When to Suspect a Rollback

**High Confidence (roll back immediately):**
- Error started within 5 minutes of deploy
- Error rate is >50% of requests
- Error is in the service that was just deployed
- Error type is NullPointerException/TypeError in new code path

**Medium Confidence (investigate first):**
- Error started 10-30 minutes after deploy
- Error rate is 10-50% of requests
- Error is in a downstream service (might be caused by new API contract)
- Error is intermittent (might be race condition)

**Low Confidence (probably not the deploy):**
- Error started >30 minutes after deploy
- Error rate is <10% of requests
- Error is in a service that wasn't deployed
- Error type is infrastructure-related (OOMKilled, connection refused)

---

## Confidence Levels

### High Confidence
- Error started immediately after deploy (<5 min)
- Clear stack trace pointing to new code
- Error is 100% reproducible
- Single error type, single service

### Medium Confidence
- Error started 5-30 minutes after deploy
- Stack trace is unclear or missing
- Error is intermittent (50-90% of requests)
- Multiple error types or services affected

### Low Confidence
- Error started >30 minutes after deploy
- No clear pattern in logs
- Error is rare (<10% of requests)
- Infrastructure-related (not application code)
- No recent deploys

---

## Quick Diagnosis Checklist

1. **Find the error line** — search for ERROR, FATAL, Exception, 5xx
2. **Get the timestamp** — when did it first appear?
3. **Check deploy history** — was there a deploy in the last 30 min?
4. **Identify the service** — which service is logging the error?
5. **Count occurrences** — is it every request or intermittent?
6. **Look up error type** — use this document to understand what it means
7. **Assess confidence** — High/Medium/Low based on patterns above
8. **Suggest actions** — rollback, investigate, or escalate