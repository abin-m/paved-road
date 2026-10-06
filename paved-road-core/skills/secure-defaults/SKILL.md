---
name: secure-defaults
description: Secure-by-default configuration for containers, Kubernetes, CI pipelines, and cloud IAM. Use when writing or reviewing a Dockerfile, k8s manifest, Helm chart, CI workflow, or IAM/role policy.
---

# secure-defaults

Each of these tools ships with unsafe defaults. Apply the settings below every time. They are a standard baseline, and they do not need a hardening project.

## Containers

```dockerfile
FROM python:3.12-slim@sha256:<digest>   # pin by digest, not floating tag
RUN adduser --system --no-create-home app
USER app                                 # never run as root
COPY --chown=app requirements.txt .
```

- Use a multi-stage build, so build tools never ship in the runtime image.
- Put no secrets in `ARG` or `ENV`. They persist in the image layers and in `docker history`.
- Add a `.dockerignore` that covers `.git`, `.env`, `*.tfvars` and `node_modules`.
- Scan before push with `trivy image <ref>`. Fail the build on a HIGH or CRITICAL finding that has a fix available.

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

- Never use `privileged: true`, `hostNetwork`, `hostPID` or a `hostPath` mount without a written reason.
- Give each namespace a default-deny `NetworkPolicy`, then allow what is needed. With no policy, every pod can reach every pod.
- Keep secrets in a real store: External Secrets, Vault or a cloud secret manager. A base64 `Secret` in git is plaintext.
- Set `automountServiceAccountToken: false` unless the pod calls the API server.
- `readinessProbe` decides whether a pod gets traffic. `livenessProbe` decides whether it restarts. A liveness probe that calls the database restarts healthy pods during a short database outage.

## CI pipelines

- Pin actions by SHA, as in `uses: actions/checkout@<sha>`, not by `@v4`.
- Give the token least privilege. Set GitHub `permissions: { contents: read }` at workflow level and widen it for each job that needs more.
- Never interpolate untrusted input into a `run:` block. `${{ github.event.pull_request.title }}` there allows remote code execution. Pass the value through `env:` and quote it.
- Scope secrets to a job and never echo them. Mask anything derived from one.
- PRs from forks must not receive secrets. Use `pull_request`, not `pull_request_target`.
- Lint, types, tests, dependency audit and image scan all fail the build. None of them only warns.

## Cloud IAM

- Never use a wildcard in both action and resource. `Action: s3:*` on `Resource: *` is a finding, and it is not an acceptable first draft.
- Prefer workload identity or OIDC federation over long-lived access keys. If a static key exists, note its rotation date.
- Give each workload its own role. Do not share one "app" role across services.
- Deny by default. Grant from the list of calls the service makes, which you get from the code or from the access-analyzer output.

## TLS and transport

- Require TLS 1.2 or later.
- Set HSTS on public endpoints.
- Never disable certificate verification. `verify=False`, `InsecureSkipVerify` and `-k` each block a review.
- Do not treat internal traffic as trusted.

## Applying this

When you review, cite the specific line and give the replacement. When you write, apply the default without comment, and mention only where you deviated and why.
