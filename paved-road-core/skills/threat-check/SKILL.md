---
name: threat-check
description: Pre-merge security review of a change, covering trust boundaries, authz, injection, secrets handling and dependency risk. Use before merging anything that touches auth, input handling, network exposure, IAM, CI config, or dependencies.
---

# threat-check

This is a threat model of one change, not a full STRIDE workshop. Run it on the diff. Each question below needs a concrete answer. Without one, the change is not ready.

## 1. Where is the trust boundary?

Name which side of this change an attacker controls. Untrusted input includes:

- request bodies, headers and query params
- filenames
- webhook payloads
- environment set by a CI job
- anything read from another service

If the diff moves data across a boundary, spend most of the review there.

## 2. Authentication and authorization

The common failure is authentication with no authorization check behind it. Missing authentication is rarer.

- Does every new endpoint or handler check that this caller may act on this object? Being logged in is not enough. It needs an object-level check such as `resource.owner_id == caller.id`. The missing check is called BOLA or IDOR, and it tops the OWASP API list.
- Are new admin or internal routes gated, or only left out of the UI?
- Does a new role or scope widen what an existing token can do? Say by how much.
- Between services, does the callee verify the caller, or does it trust the network?

## 3. Injection and deserialization

Trace where each untrusted value lands:

| Lands in | Required handling |
|---|---|
| SQL | A parameterised query. Never string interpolation, and that includes `ORDER BY` and `LIMIT`. |
| Shell | An argument list. Never `shell=True` or string concatenation. In CI, an untrusted value in a `run:` block is remote code execution. |
| Path | Resolve it and confirm the result stays under the intended root. This stops `../` traversal. |
| Templates or HTML | Escaping that fits the context. `dangerouslySetInnerHTML` or `\| safe` needs a stated reason. |
| Deserializer | `yaml.safe_load`, or JSON validated against a schema. Never `pickle`, `yaml.load` or Java native deserialization on untrusted bytes. |
| Server-side fetch (SSRF) | An allowlist for any user-supplied URL. Block link-local `169.254.169.254`, the cloud metadata address, by name. |

## 4. Secrets

- No secret literal appears in code, config, a test fixture, a CI file or a log line.
- For a new secret, say where it comes from at runtime: env from a secret store, a mounted file, or a vault. Say who can read it and how it is rotated.
- The diff does not log tokens or personal data. `logger.info(request.headers)` leaks `Authorization`.
- Error responses do not return stack traces or internal hostnames to the caller.

## 5. Dependencies and supply chain

- For a new dependency, check that it is maintained and whether it pulls in a large transitive tree. Prefer the standard library.
- Update the lockfile in the same commit. Pin CI actions by commit SHA, not by a floating tag.
- Run the project's audit: `pip-audit`, `npm audit --omit=dev` or `trivy fs .`. Report real findings only. Triage the noise, and do not paste it.

## 6. Blast radius if this is wrong

Say in one sentence what an attacker gets if this control fails. "Read of one user's own data" and "read of every tenant's data" need different levels of scrutiny before merge.

## Output

Rank findings by severity. Give each one as the location, what an attacker does there, and the fix. State what you checked and found clean. If you found nothing, say so plainly. Do not invent findings to look thorough.
