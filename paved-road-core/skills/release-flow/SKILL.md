---
name: release-flow
description: Cut, promote, verify and roll back a release. Use when tagging a version, promoting a build between environments, or reverting a bad deploy.
---

# release-flow

A release is reversible or it is a migration. Know which one you are doing before you start.

## 1. Pre-flight

- Default branch is green — the *current* run, not the last one you remember.
- Changelog reflects what actually landed (`git log <last-tag>..HEAD --oneline`).
- Version bumped per semver: breaking → major, additive → minor, fix → patch. A behaviour change in a "patch" is how consumers get burned.
- Migrations reviewed for **backward compatibility**: during rollout, old and new code run at once. Additive first (add column, backfill, then read), destructive in a *later* release. A `DROP COLUMN` in the same release as the code change makes rollback impossible.

## 2. Cut

```sh
git tag -a v1.4.0 -m "release: v1.4.0" && git push origin v1.4.0
```

Tag an immutable commit on the default branch; let CI build from the tag. The artifact is built once and promoted — never rebuilt per environment, or staging and prod are different bytes. Record the image digest, not just the tag.

## 3. Promote

Same artifact, environment-specific config only. Staging first; verify there before prod, even when it feels obvious.

Prod strategy, stated before you start:
- **Rolling** — default; needs backward-compatible schema and a working readiness probe.
- **Canary** — small share of traffic, watch error rate and p99 for a defined window before widening.
- **Blue/green** — instant switch, instant revert, double the resources.

## 4. Verify after deploy

Check the running system, not the deploy tool's exit code:

```sh
kubectl rollout status deployment/<name> --timeout=5m
curl -fsS https://<host>/healthz && curl -fsS https://<host>/version   # confirm the new version is live
```

Then watch error rate, p99 latency, and saturation for a defined soak window (10–30 min for a normal service). Log-clean plus dashboards-flat is the pass condition — not "the pods are Running".

## 5. Roll back

Decide the trigger *before* deploying ("error rate > 2% for 5 min → roll back"), so the call is not made under pressure.

```sh
kubectl rollout undo deployment/<name>
helm rollback <release> <revision>
```

Roll back first, diagnose after. If a destructive migration ran, rollback is not available — that is why step 1 splits them.

## 6. Record

Note what shipped, when, the artifact digest, and who to call. A release nobody can trace is the incident you cannot debug next week.
