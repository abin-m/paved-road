---
name: threat-check
description: Pre-merge security review of a change — trust boundaries, authz, injection, secrets handling, dependency risk. Use before merging anything that touches auth, input handling, network exposure, IAM, CI config, or dependencies.
---

# threat-check

A change-scoped threat model, not a full STRIDE workshop. Run it on the diff. Every question has a concrete answer or the change is not ready.

## 1. Where is the trust boundary?

Name it explicitly: which side of this change is attacker-controlled? Untrusted input includes request bodies, headers, query params, filenames, webhook payloads, environment set by a CI job, and **anything read from another service**. If the diff moves data across a boundary, that is the review's centre of gravity.

## 2. Authentication vs authorization

The common failure is not missing auth — it is auth without **authz**:

- Does every new endpoint/handler check that *this* caller may act on *this* object? Object-level checks (`resource.owner_id == caller.id`), not just "is logged in". This is BOLA/IDOR, top of the OWASP API list.
- Are new admin/internal routes actually gated, or only unlinked from the UI?
- Does a new role/scope widen an existing token's power? Say by how much.
- Service-to-service: is the callee verifying the caller, or trusting the network?

## 3. Injection and deserialization

Per untrusted value, trace where it lands:

- SQL → parameterised query, never string interpolation, including `ORDER BY` and `LIMIT`.
- Shell → argument list, never `shell=True` / string concat. In CI, an untrusted value in a `run:` block is remote code execution.
- Path → resolve and confirm the result stays under the intended root (`../` traversal).
- Templates/HTML → context-correct escaping; `dangerouslySetInnerHTML`/`| safe` needs a stated reason.
- Deserialization → never `pickle`/`yaml.load`/Java native on untrusted bytes. `yaml.safe_load`, JSON schema-validated.
- SSRF → any server-side fetch of a user-supplied URL needs an allowlist; block link-local `169.254.169.254` (cloud metadata) explicitly.

## 4. Secrets

- No secret literal in code, config, test fixture, CI file, or log line.
- New secret → where does it come from at runtime (env from a secret store, mounted file, vault)? Who can read it? How is it rotated?
- Check the diff does not log tokens/PII: `logger.info(request.headers)` leaks `Authorization`.
- Error responses must not return stack traces or internal hostnames to the caller.

## 5. Dependencies and supply chain

- New dependency: is it maintained, and does it pull a large transitive tree? Prefer stdlib.
- Lockfile updated in the same commit; pin CI actions by commit SHA, not a floating tag.
- Run the project's audit (`pip-audit`, `npm audit --omit=dev`, `trivy fs .`) and report real findings only — triage noise rather than pasting it.

## 6. Blast radius if this is wrong

One sentence: what does an attacker get if this control fails? "Read of one user's own data" and "read of every tenant's data" are different merges.

## Output

Report findings ranked by severity, each as: **location → what an attacker does → the fix**. State explicitly what you checked and found clean. If nothing is found, say so plainly — do not invent findings to look thorough.
