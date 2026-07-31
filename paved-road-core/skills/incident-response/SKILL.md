---
name: incident-response
description: Handle a live production incident — stabilise first, capture the timeline, diagnose, then fix and write it up. Use when something is down, degraded, or alerting in production.
---

# incident-response

Order matters: **stabilise → capture → diagnose → fix → write up.** Diagnosing a burning system before stopping the burn costs users minutes you cannot return.

## 0. Before touching anything

Note the time (UTC) and start a running log. Every command you run and every observation gets a timestamped line. The log *is* the postmortem — reconstructed timelines are fiction.

State the impact in one line: what is broken, for whom, since when. If you cannot say that yet, that is the first thing to find.

## 1. Stabilise

Restore service before understanding it. In preference order:

1. **Roll back** the most recent change (deploy, config, feature flag, infra apply). Recency is the best prior — check what shipped in the window before symptoms started.
2. **Shed load / fail over** — scale up, drain a bad node, switch traffic away.
3. **Disable the feature** — a flag off is cheaper than a fix forward.

Fix-forward only when rollback is impossible (a migration ran) or clearly slower. Announce the action before you take it if anyone else is on the system.

## 2. Capture volatile evidence

Do this *before* the restart that destroys it:

```sh
kubectl describe pod <p> ; kubectl logs <p> --previous   # previous = the crashed container
kubectl get events --sort-by=.lastTimestamp
journalctl -u <svc> --since '30 min ago'
docker inspect <c> | jq '.[].State'
```

Save the output to a file. `--previous` logs and pod events are gone after the next restart.

## 3. Diagnose

Work the four signals: saturation (CPU/mem/disk/conns), errors (rate, status codes), latency (p99, not mean), traffic (a spike, or a *drop* meaning upstream failure).

Then ask what changed: deploy, config, cert expiry, credential expiry, disk filling, a dependency's incident, a scheduled job, or traffic pattern. "Nothing changed" is almost always false — check the change log, not memory.

## 4. Fix

Smallest change that resolves it. One change at a time, verified before the next — batched changes make the cause unknowable. Verify against the user-visible symptom, not the dashboard alone.

## 5. Write up (same day)

Blameless, and mechanical rather than narrative:

- **Impact**: who, what, how long, how measured.
- **Timeline**: UTC, from first signal to resolution — straight from your log.
- **Cause**: the chain, not one word. "Cert expired" is a symptom of "no expiry monitoring".
- **Detection**: how you found out. If a user told you, that is a finding.
- **Actions**: each with an owner and an issue link. Actions with neither do not happen.

## Guardrails during an incident

Pressure is exactly when discipline slips. Still: no secrets read into context, no unreviewed writes to prod outside the stabilising action, and say plainly what you ran. If you took a shortcut, state it in the write-up rather than hiding it.
