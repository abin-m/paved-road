---
name: pipeline-debug
description: Diagnose a failing CI pipeline methodically instead of re-running it. Use when a GitHub Actions / GitLab CI job is red, flaky, or passes locally but fails in CI.
---

# pipeline-debug

Re-running is a diagnosis of "flaky" that you have not earned. Work the failure.

## 1. Read the actual failure, not the summary

Get the log of the **first** failing step — later steps fail as consequences.

```sh
gh run list --limit 5
gh run view <run-id> --log-failed          # only the failing steps
glab ci status && glab ci trace <job-id>   # GitLab
```

Find the first non-zero exit and the last command before it. Quote the error verbatim in your report; a paraphrased error is a lost error.

## 2. Classify before fixing

| Symptom | Class | First move |
|---|---|---|
| Fails in CI, passes locally | Environment drift | Diff the versions: language, OS image, lockfile state |
| Fails only sometimes, same commit | Flake | Look for time, ordering, network, or shared-state dependence |
| Fails since a specific commit | Regression | `git log` the range; reproduce that commit locally |
| Fails on all branches at once | External | Registry outage, expired token/cert, runner image bump |
| `permission denied` / `403` / `401` | Credential | Token scope or expiry — not a code problem |

Say which class this is before changing anything.

## 3. Reproduce locally with CI's environment

```sh
docker run --rm -it -v "$PWD":/w -w /w <the-image-CI-uses> bash
```

Then run the exact failing command. If it passes there, the delta is CI-only state: caches, env vars, secrets, service containers, checkout depth (`fetch-depth: 0` matters for anything reading history).

## 4. Common CI-only causes, in order of likelihood

- **Stale cache** — a cached `node_modules`/`.venv` keyed on a file that changed. Bust the key, do not delete the cache step.
- **Lockfile drift** — CI installs from the lockfile, you installed loosely. `npm ci` / `uv sync --frozen` locally to confirm.
- **Missing env var** — present in your shell, absent in CI. A secret is empty (not missing) on fork PRs.
- **Shallow clone** — tools reading tags or history need `fetch-depth: 0`.
- **Ordering / parallelism** — tests share a database or temp path. Run with `-p no:randomly` off, or `--forked`, to confirm.
- **Timezone / locale / clock** — CI is UTC, your machine is not.
- **Resource limits** — OOM kill shows as an opaque exit 137.

## 5. Fix at the right level

Fix the cause, not the symptom. `continue-on-error: true`, a bumped timeout, or a retry loop around a failing test is a suppressed signal — it needs an explicit decision and a linked follow-up issue, never a silent commit.

## 6. Confirm

Push the fix and watch the run to completion. One green run proves a deterministic fix; a flake needs several, or a demonstrated cause. Report which one you have.
