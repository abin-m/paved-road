---
name: release-flow
description: Cut, promote, verify and roll back a release. Use when tagging a version, promoting a build between environments, or reverting a bad deploy.
---

# release-flow

A release can either be rolled back or it cannot. A release that runs a destructive migration cannot. Know which kind you are doing before you start.

## 1. Pre-flight

- The default branch is green. Check the current run, not the last one you remember.
- The changelog matches what landed. Compare it with `git log <last-tag>..HEAD --oneline`.
- The version follows semver: major for a breaking change, minor for an addition, patch for a fix. A behaviour change shipped as a patch breaks consumers who trusted the number.
- Migrations are backward-compatible. During a rollout, old and new code run at the same time.

Make additive migrations first: add the column, backfill it, then read it. Ship the destructive step in a later release. A `DROP COLUMN` in the same release as the code change makes rollback impossible.

## 2. Cut

```sh
git tag -a v1.4.0 -m "release: v1.4.0" && git push origin v1.4.0
```

Tag an immutable commit on the default branch, and let CI build from the tag. Build the artifact once and promote it. If you rebuild for each environment, staging and production run different bytes. Record the image digest as well as the tag.

## 3. Promote

Promote the same artifact, and change only the config for each environment. Deploy to staging first and verify there before production, even when the change looks obvious.

State the production strategy before you start:

- Rolling is the default. It needs a backward-compatible schema and a working readiness probe.
- Canary sends a small share of traffic to the new version. Watch the error rate and p99 for a defined window before you widen it.
- Blue/green switches at once and reverts at once. It needs double the resources.

## 4. Verify after deploy

Check the running system, not the deploy tool's exit code:

```sh
kubectl rollout status deployment/<name> --timeout=5m
curl -fsS https://<host>/healthz && curl -fsS https://<host>/version   # confirm the new version is live
```

Then watch the error rate, p99 latency and saturation for a defined soak window. For a normal service that is 10 to 30 minutes. The release passes when the logs are clean and the dashboards are flat. Pods in the Running state do not prove that.

## 5. Roll back

Decide the trigger before you deploy, for example "roll back if the error rate is above 2% for 5 minutes". Then nobody has to make the call under pressure.

```sh
kubectl rollout undo deployment/<name>
helm rollback <release> <revision>
```

Roll back first and diagnose afterwards. If a destructive migration ran, you cannot roll back. Step 1 splits migrations for that reason.

## 6. Record

Note what shipped, when, the artifact digest, and who to call. Without that record, nobody can trace next week's incident back to this release.
