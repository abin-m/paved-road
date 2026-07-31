---
name: secure-defaults
description: Secure-by-default configuration for containers, Kubernetes, CI pipelines, and cloud IAM. Use when writing or reviewing a Dockerfile, k8s manifest, Helm chart, CI workflow, or IAM/role policy.
---

# secure-defaults

The defaults are wrong in every one of these tools. These are the deltas worth applying every time — the paved road, not a bespoke hardening exercise.

## Containers

```dockerfile
FROM python:3.12-slim@sha256:<digest>   # pin by digest, not floating tag
RUN adduser --system --no-create-home app
USER app                                 # never run as root
COPY --chown=app requirements.txt .
```

- Multi-stage build: build tools never ship in the runtime image.
- No secrets in `ARG`/`ENV` — they persist in the image layers and `docker history`.
- `.dockerignore` covering `.git`, `.env`, `*.tfvars`, `node_modules`.
- Scan before push (`trivy image <ref>`); fail the build on HIGH/CRITICAL with a fix available.

## Kubernetes

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities: { drop: ["ALL"] }
resources:
  requests: { cpu: 50m, memory: 128Mi }
  limits:   { memory: 512Mi }        # memory limit yes; CPU limit usually no (throttling)
```

- Never `privileged: true`, `hostNetwork`, `hostPID`, or a `hostPath` mount without a written reason.
- Default-deny `NetworkPolicy` per namespace, then allow what is needed. No policy = every pod can reach every pod.
- Secrets via a real store (External Secrets, Vault, cloud secret manager) — a base64 `Secret` in git is plaintext.
- Set `automountServiceAccountToken: false` unless the pod calls the API server.
- Probes: `readinessProbe` decides traffic, `livenessProbe` decides restart. A liveness probe that hits the database restarts healthy pods during a DB blip.

## CI pipelines

- Pin actions by SHA (`uses: actions/checkout@<sha>`), not `@v4`.
- Least-privilege token: GitHub `permissions: { contents: read }` at workflow level, widen per job.
- Never interpolate untrusted input into a `run:` block (`${{ github.event.pull_request.title }}` is RCE) — pass via `env:` and quote.
- Secrets are job-scoped and never echoed; mask anything derived from one. Fork PRs must not receive secrets (`pull_request`, not `pull_request_target`).
- The pipeline is the gate: lint, types, tests, dependency audit, and image scan all fail the build, not warn.

## Cloud IAM

- No wildcards in both action *and* resource. `Action: s3:*` on `Resource: *` is a finding, not a starting point.
- Prefer workload identity / OIDC federation over long-lived access keys. If a static key exists, note its rotation date.
- Separate roles per workload; no shared "app" role across services.
- Deny by default; grant from the list of calls the service actually makes (read the code, or the access-analyzer output).

## TLS and transport

TLS 1.2 minimum, HSTS on public endpoints, certificate verification never disabled (`verify=False`, `InsecureSkipVerify`, `-k` are review-stoppers). Internal traffic is not "trusted" traffic.

## Applying this

When reviewing, cite the specific line and give the replacement. When writing, apply the default silently and mention only where you deviated and why.
