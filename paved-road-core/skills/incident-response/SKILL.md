---
name: incident-response
description: Handle a live production incident. Stabilise first, capture the timeline, diagnose, then fix and write it up. Use when something is down, degraded, or alerting in production.
---

# incident-response

Work in this order: stabilise, capture, diagnose, fix, write up. Stop the damage before you look for the cause. Every minute spent diagnosing a system that is still failing is a minute of outage for its users.

## 0. Before touching anything

Note the time in UTC and start a running log. Give every command you run and every observation a timestamped line. The write-up comes from this log. A timeline rebuilt from memory afterwards is unreliable.

State the impact in one line: what is broken, for whom, since when. If you cannot say that yet, find it out first.

## 1. Stabilise

Restore service before you understand the failure. Try these in order:

1. Roll back the most recent change: a deploy, a config change, a feature flag or an infra apply. The most recent change is the most likely cause, so check what shipped just before the symptoms started.
2. Shed load or fail over. Scale up, drain a bad node, or switch traffic away.
3. Disable the feature. Turning a flag off is cheaper than shipping a fix.

Fix forward only when a rollback is impossible, for example after a migration ran, or when it is clearly slower. If anyone else is on the system, announce the action before you take it.

## 2. Capture volatile evidence

Do this before the restart that destroys it:

```sh
kubectl describe pod <p> ; kubectl logs <p> --previous   # previous = the crashed container
kubectl get events --sort-by=.lastTimestamp
journalctl -u <svc> --since '30 min ago'
docker inspect <c> | jq '.[].State'
```

Save the output to a file. `--previous` logs and pod events are gone after the next restart.

## 3. Diagnose

Check four signals:

- Saturation: CPU, memory, disk, connections.
- Errors: rate and status codes.
- Latency: p99, not the mean.
- Traffic: a spike, or a drop that points to an upstream failure.

Then ask what changed. Candidates are a deploy, a config change, an expired certificate or credential, a filling disk, a dependency's incident, a scheduled job, or a new traffic pattern. "Nothing changed" is almost always false. Check the change log, not your memory.

## 4. Fix

Make the smallest change that resolves it. Make one change at a time and verify it before the next. After a batch of changes you cannot tell which one worked. Verify against the symptom the user sees, not the dashboard alone.

## 5. Write up, the same day

Keep it blameless. Report facts in a fixed structure, and do not tell a story.

- Impact: who was affected, what failed, for how long, and how you measured it.
- Timeline: in UTC, from the first signal to resolution, copied from your log.
- Cause: the chain of causes, not one word. "Cert expired" is a symptom of "no expiry monitoring".
- Detection: how you found out. If a user told you, that is a finding.
- Actions: each with an owner and an issue link. An action with neither does not get done.

The `writing` skill says how an incident write-up should open.

## Guardrails during an incident

Discipline slips under pressure, so these rules still hold:

- Read no secrets into context.
- Make no unreviewed writes to production, apart from the stabilising action.
- Say plainly what you ran.

If you took a shortcut, state it in the write-up.
