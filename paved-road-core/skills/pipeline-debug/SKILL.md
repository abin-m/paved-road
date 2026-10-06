---
name: pipeline-debug
description: Diagnose a failing CI pipeline methodically instead of re-running it. Use when a GitHub Actions or GitLab CI job is red, flaky, or passes locally but fails in CI.
---

# pipeline-debug

Re-running a failed job assumes the failure is a flake. Do not assume that. Find the cause.

## 1. Read the actual failure, not the summary

Get the log of the first failing step. Later steps fail as a consequence of it.

```sh
gh run list --limit 5
gh run view <run-id> --log-failed          # only the failing steps
glab ci status && glab ci trace <job-id>   # GitLab
```

Find the first non-zero exit and the last command before it. Quote the error verbatim in your report. A paraphrase loses the detail that identifies the cause.

## 2. Classify before fixing

| Symptom | Class | First move |
|---|---|---|
| Fails in CI, passes locally | Environment drift | Diff the versions: language, OS image, lockfile state |
| Fails only sometimes, same commit | Flake | Look for time, ordering, network, or shared-state dependence |
| Fails since a specific commit | Regression | `git log` the range, then reproduce that commit locally |
| Fails on all branches at once | External | Registry outage, expired token or cert, runner image bump |
| `permission denied`, `403` or `401` | Credential | Check token scope and expiry. The code is not the problem |

Say which class this is before you change anything.

## 3. Reproduce locally with CI's environment

```sh
docker run --rm -it -v "$PWD":/w -w /w <the-image-CI-uses> bash
```

Then run the exact failing command. If it passes there, the difference is state that only CI has: caches, env vars, secrets, service containers or checkout depth. `fetch-depth: 0` matters for anything that reads history.

## 4. Common CI-only causes, most likely first

- Stale cache. A cached `node_modules` or `.venv` is keyed on a file that changed. Change the cache key. Do not delete the cache step.
- Lockfile drift. CI installs from the lockfile and you installed loosely. Run `npm ci` or `uv sync --frozen` locally to confirm.
- Missing env var. It is set in your shell and absent in CI. On a PR from a fork, a secret is empty, not missing.
- Shallow clone. Tools that read tags or history need `fetch-depth: 0`.
- Ordering or parallelism. Tests share a database or a temp path. Run with `-p no:randomly` off, or with `--forked`, to confirm.
- Timezone, locale or clock. CI runs in UTC and your machine does not.
- Resource limits. An out-of-memory kill shows only as exit code 137.

## 5. Fix at the right level

Fix the cause, not the symptom. `continue-on-error: true`, a longer timeout, or a retry loop around a failing test each hide the failure. Any of them needs an explicit decision and a linked follow-up issue. Never commit one without saying so.

## 6. Confirm

Push the fix and watch the run to the end. One green run proves a deterministic fix. A flake needs several green runs, or a cause you have demonstrated. Report which of the two you have.
